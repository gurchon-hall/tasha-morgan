"""Lucinde, Alastor (crypt vampire ability). krcg id 201700.

Card text (verbatim, via the installed `krcg` package's own
`krcg.vtes.VTES[201700].card_text`, confirmed live 2026-10-15 against
`https://api.krcg.org/card/201700`): "Camarilla Ventrue Justicar: During
your master phase, Lucinde can burn 1 blood to choose a vampire; this
turn, Camarilla vampires you control can enter combat with the chosen
vampire as a Ⓓ action. +1 bleed." Ventrue, Justicar, group 7, capacity 10
(the `201700`/group-7 printing; a distinct group-3 printing, krcg id
200873, is a different card and out of scope here).

Ruling (verbatim, via krcg, matching the live API): "The ability can be
used when in torpor. [LSJ 20011022]" -- so the `MASTER_PHASE_ABILITY_HOOK`
provider below gates on Lucinde's own `zone in ("ready", "torpor")` (in
play at all, per the Rulebook §8 glossary "Target" rule cited below), never
on `is_ready_unlocked`/`locked`.

"During your master phase, ... can burn 1 blood to choose a vampire":
Rulebook §3 "Wording templates" > "'During X, do Y': ... only one Y can be
done per X with this card" (`data/sources/rulebook/2026-10-09/
3-playing-the-game.md` lines 86-91) -- X is "your master phase" (one per
turn), so this caps the ability at once per turn per Lucinde instance.
Enforced via `VampireInPlay.ability_used_turn` (its own docstring: "generic
'once per X' scratch ... keyed by a provider-chosen string, storing the
turn number"), not a hand-rolled cap -- a Rulebook-settled fact, not a
guess. Per the master phase ability ruling above, activating costs no
master-phase action (`MASTER_PHASE_ABILITY_HOOK`'s own contract).

"choose a vampire" (no "ready"/"opposing" qualifier): Rulebook §8 glossary
"Target": "If a card is played on another card, or targets another card,
the target card must be in play (that is, controlled). Vampires in the
torpor region are eligible targets by default, but vampires in the
uncontrolled region and contested cards are not" (quoted verbatim in
`cards/celerity.py`'s own docstring, same rule, first applied there) --
so the legal pool is the opponent's vampires with `zone in ("ready",
"torpor")`, excluding `"uncontrolled"` (face-down, identity hidden per
`engine/observation.py`) and `"burned"`/`"removed_from_game"`. The
glossary's own "contested cards are not [eligible]" clause is overridden
here by the 2P variant's own delta (CLAUDE.md §3: "Contested crypt cards:
stays in play, usable") -- a contested vampire is not excluded on that
ground in this format. Unlike `cards/line_brawl.py`'s own `[pot]` clause
(whose target choice *is* the combat initiation, so it restricts to
`zone == "ready"` -- only a ready vampire can actually be forced into
combat, Rulebook §4 "Leave Torpor"), Lucinde's own choice does not itself
initiate combat; it only binds a target for a *later, independent* grant
(`EnterCombatGrant`), whose own consumer (the `ACTION_CARD_PLAY_HOOK`
provider below) re-checks `zone == "ready"` at the time a Camarilla
vampire actually tries to use the grant. Restricting Lucinde's own choice
to "ready" would be copying `line_brawl.py`'s gate for a reason that does
not apply to this different timing (a target who is merely in torpor right
now could still be ready again later this same turn, e.g. after an Edge
unlock-related effect this project does not yet model -- not excluding it
up front loses nothing and matches the glossary's own default).

With no eligible opponent vampire at all (e.g. the opponent controls no
in-play vampire), the ability is not offered -- same "never offer a play
that cannot resolve" convention as `line_brawl.py`'s own
`_eligible_combat_targets` guard. With exactly one eligible target, it is
bound directly, no `Decision` raised; with more than one, a `Decision`
offers one choice per target (same shape as `line_brawl.py`'s `[pot]`
clause).

"this turn, Camarilla vampires you control can enter combat with the
chosen vampire as a Ⓓ action": wired against `engine/phases/minion.py`'s
`grant_enter_combat_this_turn`/`active_enter_combat_grants`/
`build_enter_combat_action_spec` (first production user of these
primitives, alongside the generic scenario tests in `tests/rules/
test_enter_combat_grant.py`). "Camarilla vampires you control": a
card-level gate on `vampire.card.sect is Sect.CAMARILLA` on the *acting*
vampire trying to use the grant (same shape as `line_brawl.py`'s own
"Requires an Anarch" gate), independent of whether that vampire is Lucinde
herself (nothing excludes her; she is herself Camarilla). Each active
grant is offered as its own `ACTION_CARD_PLAY_HOOK` option, gated at offer
time on the grant's target still being `zone == "ready"` (mirrors
`line_brawl.py`'s own `_eligible_combat_targets` guard) -- a target who
has since left `torpor` and *entered* `ready` is fine (no printed
restriction says otherwise), one who is now `torpor`/gone is simply not
offered. No card is played by this option (`played_card_type` stays at
its default `None`).

"+1 bleed": flat, unconditional `BLEED_AMOUNT_FIXED_MODIFIER_HOOK`
contribution, gated only on this vampire being the one bleeding -- mirrors
`cards/diana_iadanza.py`'s own identically-shaped trailing "+1 bleed"
clause byte for byte.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.cards import Sect
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.master import MASTER_PHASE_ABILITY_HOOK
from vtesbot.engine.phases.minion import (
    ACTION_CARD_PLAY_HOOK,
    BLEED_AMOUNT_FIXED_MODIFIER_HOOK,
    active_enter_combat_grants,
    build_enter_combat_action_spec,
    grant_enter_combat_this_turn,
)
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 201700
BLOOD_COST = 1
"""Printed "burn 1 blood"."""
ABILITY_USED_KEY = "lucinde_alastor_choose_vampire"
"""`VampireInPlay.ability_used_turn` key: once-per-master-phase cap, per the
Rulebook "During X, do Y" wording template (module docstring)."""
IN_PLAY_ZONES = ("ready", "torpor")
"""Rulebook §8 glossary "Target": in play means ready or torpor, never
uncontrolled/burned/removed (module docstring)."""


def _lucinde_instances(state: GameState, player: str) -> list[VampireInPlay]:
    return [
        v
        for v in state.players[player].vampires.values()
        if v.card.krcg_id == KRCG_ID and v.zone in IN_PLAY_ZONES
    ]


def _eligible_choose_targets(state: GameState, opponent: str) -> list[VampireInPlay]:
    """The legal "choose a vampire" pool: the opponent's in-play vampires
    (module docstring's Rulebook §8 "Target" citation)."""
    return [v for v in state.players[opponent].vampires.values() if v.zone in IN_PLAY_ZONES]


def _provide_lucinde_master_ability(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "During your master phase, Lucinde can burn 1 blood to choose a
    vampire; this turn, Camarilla vampires you control can enter combat
    with the chosen vampire as a Ⓓ action." -- see module docstring for the
    torpor-usable gate, the once-per-master-phase cap, and the target pool.
    """
    player = context["player"]
    opponent = state.other_player(player)
    options: list[HookOption] = []
    for lucinde in _lucinde_instances(state, player):
        if lucinde.blood < BLOOD_COST:
            continue
        if lucinde.ability_used_turn.get(ABILITY_USED_KEY) == state.turn_number:
            continue
        if not _eligible_choose_targets(state, opponent):
            continue  # never offer a play that cannot resolve (line_brawl.py precedent).

        def _apply(s: GameState, lucinde: VampireInPlay = lucinde) -> bool:
            lucinde.blood -= BLOOD_COST
            lucinde.ability_used_turn[ABILITY_USED_KEY] = s.turn_number
            targets = _eligible_choose_targets(s, opponent)
            if len(targets) == 1:
                target_id = targets[0].instance_id
            else:
                choices = tuple(
                    Choice(f"lucinde_alastor_target:{v.instance_id}", f"Choose {v.card.name}")
                    for v in targets
                )
                decision = Decision(player=player, kind="lucinde_alastor_target", choices=choices)
                chosen_value = s.ask(decision).value
                target_id = chosen_value.split(":", 1)[1]
            grant_enter_combat_this_turn(
                s, player, target_player=opponent, target_vampire_id=target_id
            )
            return False  # irrelevant: never read for a master_phase_ability option.

        options.append(
            HookOption(
                choice=Choice(
                    f"lucinde_alastor_ability:{lucinde.instance_id}",
                    "Lucinde, Alastor: burn 1 blood to choose a vampire",
                ),
                apply=_apply,
            )
        )
    return options


def _controllers_vampire(state: GameState, context: Mapping[str, Any]) -> VampireInPlay | None:
    return state.players[context["player"]].vampires.get(context["vampire"])


def _provide_lucinde_enter_combat_grant(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "Camarilla vampires you control can enter combat with the chosen
    vampire as a Ⓓ action" -- one option per active grant whose target is
    still `zone == "ready"` right now (module docstring)."""
    player = context["player"]
    vampire = _controllers_vampire(state, context)
    if vampire is None or vampire.card.sect is not Sect.CAMARILLA:
        return []
    options: list[HookOption] = []
    for grant in active_enter_combat_grants(state, player):
        target = state.players[grant.target_player].vampires.get(grant.target_vampire_id)
        if target is None or target.zone != "ready":
            continue  # never offer a play that cannot resolve (line_brawl.py precedent).

        def _apply(s: GameState, grant: Any = grant, vampire: VampireInPlay = vampire) -> Any:
            return build_enter_combat_action_spec(
                s, player, vampire, grant.target_player, grant.target_vampire_id
            )

        options.append(
            HookOption(
                choice=Choice(
                    f"lucinde_alastor_enter_combat:{vampire.instance_id}:{grant.target_vampire_id}",
                    f"Enter combat with {target.card.name} (Lucinde, Alastor)",
                ),
                apply=_apply,
            )
        )
    return options


def _provide_lucinde_bleed(state: GameState, context: Mapping[str, Any]) -> int:
    """ "+1 bleed" -- mirrors `cards/diana_iadanza.py`'s own identical
    trailing clause."""
    player = context["player"]
    vampire = state.players[player].vampires.get(context["vampire"])
    if vampire is None or vampire.card.krcg_id != KRCG_ID:
        return 0
    return 1


hooks.register(MASTER_PHASE_ABILITY_HOOK, _provide_lucinde_master_ability)
hooks.register(ACTION_CARD_PLAY_HOOK, _provide_lucinde_enter_combat_grant)
hooks.register(BLEED_AMOUNT_FIXED_MODIFIER_HOOK, _provide_lucinde_bleed)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Lucinde, Alastor",
        status=Status.IMPLEMENTED,
        hooks=(Hook.MASTER_PHASE_ABILITY, Hook.ACTION_CARD_PLAY, Hook.BLEED_AMOUNT_FIXED_MODIFIER),
        source=__name__,
    )
)
