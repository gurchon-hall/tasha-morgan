"""Fleetness (Action). krcg id 100747.

Card text (verbatim, via the installed `krcg` 5.14+ package's own
`krcg.load()["Fleetness"].text`, 2026-10-12, matching the raw snapshot saved
to `data/cards/100747.json` byte-for-byte, cross-checked live against
`https://api.krcg.org/card/100747`):
    "+1 stealth action.
    [cel] Ⓓ Bleed.
    [CEL] Ⓓ Enter combat with a locked minion. This acting vampire gets 1
    optional maneuver during that combat."

Ruling (verbatim, one on file, both the installed package and the live API
agree):
    - "[CEL]If the action is unblocked when it resolves and the target is
      unlocked, the action "fizzles" (cost, if any, is paid, and it is
      considered successful, but has no effect)." [ANK 20210124]
      [LSJ 20070411] [LSJ 20090514] (ruling `group`: "Action targeting
      locked minion").

Card type: Action (`types == ["Action"]`, *not* "Action Modifier" -- this is
itself the acting vampire's entire minion action for the turn, same category
as Enchant Kindred/Line Brawl). `discipline_requirement == {"type": "Mono",
"disciplines": ["cel"]}` (basic Celerity required to play the card at all;
superior Celerity, printed uppercase "CEL" on a `CryptCard`, additionally
unlocks the second, bracketed clause -- Rulebook §3 "Discipline symbol
within a diamond ... may opt to use either the basic (plain text) or the
superior (bold) effect ... but not both"). `clan_requirement == []`,
`path_requirement == []`, `burn_option is False`, `trifle is False` (no bonus
master-phase/minion-phase action; this is an ordinary minion action).
`cost == {"type": "Blood", "value": 1}`: a genuine *blood* cost, printed in
the top card-frame cost box, independent of which discipline-level clause is
used (both clauses below pay it). Rulebook §2 Card Types > "Requirements for
Playing Cards" (verbatim, `data/sources/rulebook/2026-10-09/
2-card-types.md:155-157`): "A number in a red drop represents blood cost (the
amount of blood the vampire must burn). Only a vampire with enough blood on
them can play a card with a blood cost." -- i.e. the *acting vampire itself*
(not the Methuselah's pool) must have at least 1 blood to play this card at
all; this is a precondition for legally playing the card, checked at offer
time, independent of whether the cost is actually paid. Rulebook §4 Minion
Phase > Detailed Course of an Action (verbatim, quoted already by
`src/vtesbot/engine/action.py`'s own module docstring, step 3): "If
unblocked -> pay cost, resolve. If blocked -> action card burned, cost not
paid, blocker locks, combat." -- so the 1 blood is burned from the acting
vampire only if the action resolves unblocked (mirrors
`_perform_recruit_ally`'s own `RecruitAllySpec.pay_cost`, paid only on the
unblocked branch), never deducted merely for announcing the play. The
`[CEL]` clause's own ruling above confirms the same holds even when that
clause's own effect goes on to fizzle: "cost, if any, is paid" regardless --
paid inside `resolve()` *before* the fizzle check below, not conditioned on
it.

Legal since 2008-12-19; confirmed on the active 2P allowed list (`data/
formats/2p/2026-10-03.json`, krcg id 100747).

Prey/predator wording check (per the `implement-card` skill, step 3): both
clauses carry the "Ⓓ" marker, Rulebook glossary "Directed Action" (targets
one other Methuselah). In a 2P duel this collapses to the single-opponent
block-attempt model (CLAUDE.md §3; same reading as `enchant_kindred.py`'s
basic clause). Not OQ-1.

Status: implemented. Previously `blocked` (OQ-25, resolved) for want of a
way to pre-grant a one-shot, this-combat-only optional maneuver at announce
time, before the block-attempt window opens. `rules-engineer`'s fix:
`engine/combat.py::run_combat` gained an optional `initial_combat_state`
parameter plus `seed_pre_combat_maneuver_grant`/
`pre_combat_maneuver_available`/`consume_pre_combat_maneuver_grant` helpers
keyed by `PRE_COMBAT_MANEUVER_GRANT_KEY`; `engine/phases/minion.py::
ActionCardSpec` gained a `maneuver_grant` field, threaded by `engine/
action.py::perform_minion_action`'s own `maneuver_grant` parameter into its
internal `run_combat` call on the blocked branch -- see those modules' own
docstrings for the mechanism, proven generically by `tests/rules/
test_pre_combat_maneuver_grant.py`. OQ-57 (`docs/OPEN_QUESTIONS.md`): both
clauses call `remove_from_hand` (not `play_from_hand`) and set `ActionCard
Spec.name=NAME`, so `engine/phases/minion.py::_perform_action_card` can
interleave a future Reflex card's own cancel-as-played window before
drawing the replacement (Finding 1), and so a second physical copy is not
offered once either clause has already been played this turn (Finding 2,
keyed by `NAME` -- both clauses are the same physical card).

"+1 stealth action." / "[cel] Ⓓ Bleed.": printed before either bracketed
clause (unlike Enchant Kindred's own superior-only "+1 stealth action"), so
this baseline applies regardless of which clause is used -- both clauses
below carry `base_stealth=1`. The basic clause is a plain directed,
default-amount (1) bleed -- no "+1 bleed" bonus printed here, unlike
Enchant Kindred's/Line Brawl's `[pre]` clauses -- mirroring
`_perform_bleed`'s own `resolve` closure so other bleed-amount cards still
compose on top. `ActionCardSpec.action` is declared `ACTION_BLEED` (OQ-17
follow-up requirement) so a bleed-gated provider sharing the same hook
windows (e.g. `bonding.py`'s superior clause) isn't silently suppressed.
The printed 1-blood cost is burned from the acting vampire at the start of
`resolve()`, before the bleed computation -- only reached on the unblocked
branch (Rulebook §4 step 3, quoted in `engine/action.py`'s module
docstring: cost is paid only if unblocked).

"[CEL] Ⓓ Enter combat with a locked minion. This acting vampire gets 1
optional maneuver during that combat.": the "enter combat" half is the same
shape as `line_brawl.py`'s `[pot]` clause, with one extra target filter --
"a locked minion" restricts the announce-time target choice to the
opponent's `zone == "ready"` *and* `locked == True` vampires (the Ⓓ marker
ties block eligibility to the targeted Methuselah, not the named minion,
and a locked vampire is never itself a legal blocker,
`attempt_block`'s own `ready_unlocked_vampires` list). The on-file ruling
("unblocked ... target is unlocked ... fizzles") is the OQ-21 fizzle
convention: `resolve()` re-validates the target is still ready-and-locked
before acting, doing nothing further otherwise. "Gets 1 optional maneuver
during that combat" is the OQ-25 pre-combat grant:
`ActionCardSpec.maneuver_grant=acting_vampire.instance_id` (blocked branch,
threaded by `perform_minion_action`) and `resolve()`'s own direct
`run_combat` call (unblocked branch) both seed
`seed_pre_combat_maneuver_grant(acting_vampire.instance_id)`. The generic
`"maneuver"` hook provider `_provide_fleetness_maneuver` below recognizes
the seeded grant via `pre_combat_maneuver_available`/
`consume_pre_combat_maneuver_grant` and offers/claims it, mirroring
`tests/rules/test_pre_combat_maneuver_grant.py`'s fake provider.

The target is chosen inside `apply()`, at announce time (Rulebook §4
"Announce the Action" + `ActionCardSpec` contract; same timing as
`line_brawl.py`'s `[pot]` clause, OQ-21). With exactly one eligible locked
target it is bound directly with no decision raised; with none, the clause
is not offered at all; with more than one, a `Decision`
(`"fleetness_combat_target"`) offers one choice per target.

Basic vs superior discipline gating mirrors `enchant_kindred.py`'s/
`line_brawl.py`'s convention: reads `card.disciplines` (plain printed stat,
not attachment-aware `effective_disciplines` -- OQ-8 noted, not acted on
here, matching those precedents). The basic `[cel]` clause is offered
whenever the acting vampire has either `"cel"` or `"CEL"` (superior unlocks
either effect, Rulebook §3); the superior `[CEL]` clause only with `"CEL"`.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import remove_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import ACTION_BLEED
from vtesbot.engine.combat import (
    MANEUVER_HOOK,
    consume_pre_combat_maneuver_grant,
    pre_combat_maneuver_available,
    run_combat,
    seed_pre_combat_maneuver_grant,
)
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import (
    ACTION_CARD_PLAY_HOOK,
    BLEED_AMOUNT,
    BLEED_AMOUNT_FIXED_MODIFIER_HOOK,
    BLEED_AMOUNT_MODIFIER_HOOK,
    PENDING_BLEED_AMOUNT_KEY,
    ActionCardSpec,
    action_card_already_played_this_turn,
)
from vtesbot.engine.pool import lose_pool
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 100747
NAME = "Fleetness"
"""`ActionCardSpec.name`/`CardRegistration.name` (OQ-57, `docs/
OPEN_QUESTIONS.md`): the generic "same named action card at most once per
turn" cap is keyed by this exact string for both clauses -- they are the
same physical card."""
BASIC = "cel"
SUPERIOR = "CEL"
STEALTH = 1
"""Printed "+1 stealth action." baseline -- applies to the action regardless
of which clause is used (module docstring)."""
BLOOD_COST = 1
"""Printed blood-cost box: burned from the acting vampire, only on the
unblocked branch, independent of which clause is used (module docstring)."""
CARD_TYPE = "Action"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): matches
this module's own "Card type: Action" docstring fact above -- set on both
`ACTION_CARD_PLAY_HOOK` options (the card actually being played); the
`MANEUVER_HOOK` provider (`_provide_fleetness_maneuver`) only claims an
already-seeded pre-combat grant from a Fleetness already played and paid
for earlier this action, so it leaves `HookOption.played_card_type` at its
default `None` (see that field's own docstring)."""


def _controllers_vampire(state: GameState, context: Mapping[str, Any]) -> VampireInPlay | None:
    """The acting vampire for this `"action_card_play"` offer, or `None` if
    `context["player"]` is the defender for this particular hook call (the
    same hook is offered to both sides over the course of a game)."""
    return state.players[context["player"]].vampires.get(context["vampire"])


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _eligible_locked_targets(state: GameState, player: str) -> list[VampireInPlay]:
    """Opposing vampires the `[CEL]` clause could force into combat: "a
    locked minion" -- `zone == "ready"` (torpor is the only readiness
    restriction any "enter combat" text carries, `line_brawl.py`'s own
    module docstring) *and* `locked == True`."""
    opponent = state.other_player(player)
    return [v for v in state.players[opponent].vampires.values() if v.zone == "ready" and v.locked]


def _provide_fleetness_basic(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "+1 stealth action. [cel] Ⓓ Bleed." -- a directed, default-amount
    bleed, +1 stealth baseline, 1-blood cost."""
    player = context["player"]
    acting_vampire = _controllers_vampire(state, context)
    if acting_vampire is None:
        return []
    disciplines = acting_vampire.card.disciplines
    if BASIC not in disciplines and SUPERIOR not in disciplines:
        return []
    if not _has_card_in_hand(state, player):
        return []
    if acting_vampire.blood < BLOOD_COST:
        return []  # printed blood cost: must have enough blood to play at all.
    if action_card_already_played_this_turn(state, acting_vampire, NAME):
        return []  # OQ-57 Finding 2: same named action card, once per turn.

    def _apply(s: GameState) -> ActionCardSpec:
        remove_from_hand(s, player, KRCG_ID)

        def resolve(pending: dict[str, Any]) -> None:
            other = s.other_player(player)
            acting_vampire.blood -= BLOOD_COST  # paid now: action resolved unblocked.
            base_amount = (
                BLEED_AMOUNT
                + hooks.sum_modifiers(
                    BLEED_AMOUNT_FIXED_MODIFIER_HOOK,
                    s,
                    player=player,
                    vampire=acting_vampire.instance_id,
                )
                + pending.get(PENDING_BLEED_AMOUNT_KEY, 0)
            )
            amount_box = [base_amount]
            hooks.resolve_impulse_window(
                s,
                BLEED_AMOUNT_MODIFIER_HOOK,
                player,
                other,
                context={
                    "vampire": acting_vampire.instance_id,
                    "amount": amount_box,
                    "pending": pending,
                },
            )
            amount = max(0, amount_box[0])
            lose_pool(s, other, amount)
            if amount >= 1:
                s.edge_holder = player

        return ActionCardSpec(
            base_stealth=STEALTH,
            directed=True,
            resolve=resolve,
            action=ACTION_BLEED,
            name=NAME,
        )

    return [
        HookOption(
            choice=Choice("fleetness:basic", "Fleetness [cel]: +1 stealth action. Bleed"),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


def _provide_fleetness_superior(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "+1 stealth action. [CEL] Ⓓ Enter combat with a locked minion. This
    acting vampire gets 1 optional maneuver during that combat." -- see
    module docstring for the target-choice decision, the OQ-21 fizzle
    convention, and the OQ-25 pre-combat maneuver grant."""
    player = context["player"]
    acting_vampire = _controllers_vampire(state, context)
    if acting_vampire is None:
        return []
    if SUPERIOR not in acting_vampire.card.disciplines:
        return []
    if not _has_card_in_hand(state, player):
        return []
    if acting_vampire.blood < BLOOD_COST:
        return []  # printed blood cost: must have enough blood to play at all.
    if not _eligible_locked_targets(state, player):
        return []  # no legal target: do not offer a card play that cannot resolve.
    if action_card_already_played_this_turn(state, acting_vampire, NAME):
        return []  # OQ-57 Finding 2: same named action card, once per turn.

    def _apply(s: GameState) -> ActionCardSpec:
        remove_from_hand(s, player, KRCG_ID)
        opponent = s.other_player(player)

        # Target fixed at announce time, not deferred to resolve() -- OQ-21,
        # see module docstring.
        targets = _eligible_locked_targets(s, player)
        if len(targets) == 1:
            target_id = targets[0].instance_id
        else:
            choices = tuple(
                Choice(
                    f"fleetness_combat_target:{v.instance_id}",
                    f"Enter combat with {v.card.name}",
                )
                for v in targets
            )
            decision = Decision(player=player, kind="fleetness_combat_target", choices=choices)
            chosen_value = s.ask(decision).value
            target_id = chosen_value.split(":", 1)[1]

        def resolve(pending: dict[str, Any]) -> None:
            del pending  # no later hook window of its own to feed.
            # Cost is paid regardless of the fizzle outcome below -- the
            # ruling on file: "cost, if any, is paid" even when the action
            # fizzles (module docstring).
            acting_vampire.blood -= BLOOD_COST
            target = s.players[opponent].vampires.get(target_id)
            if target is None or target.zone != "ready" or not target.locked:
                return  # fizzles (ruling + OQ-21 convention): no further effect.
            run_combat(
                s,
                player,
                acting_vampire,
                opponent,
                target,
                seed_pre_combat_maneuver_grant(acting_vampire.instance_id),
            )

        return ActionCardSpec(
            base_stealth=STEALTH,
            directed=True,
            resolve=resolve,
            maneuver_grant=acting_vampire.instance_id,
            name=NAME,
        )

    return [
        HookOption(
            choice=Choice(
                "fleetness:superior",
                "Fleetness [CEL]: +1 stealth action. "
                "Enter combat with a locked minion. Gets 1 optional maneuver",
            ),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


def _provide_fleetness_maneuver(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """Generic `"maneuver"` hook provider recognizing a seeded pre-combat
    grant (module docstring's OQ-25 paragraph) -- offers exactly when
    `context["vampire"]` currently has an unclaimed pre-combat grant, via the
    shared `pre_combat_maneuver_available`/`consume_pre_combat_maneuver_
    grant` helpers (never reading/writing `combat_state` directly), mirroring
    `tests/rules/test_pre_combat_maneuver_grant.py`'s own fake stand-in."""
    del state
    if not pre_combat_maneuver_available(context):
        return []

    def _use(s: GameState) -> None:
        del s
        consume_pre_combat_maneuver_grant(context)

    return [
        HookOption(choice=Choice("fleetness:maneuver", "Fleetness: optional maneuver"), apply=_use)
    ]


hooks.register(ACTION_CARD_PLAY_HOOK, _provide_fleetness_basic)
hooks.register(ACTION_CARD_PLAY_HOOK, _provide_fleetness_superior)
hooks.register(MANEUVER_HOOK, _provide_fleetness_maneuver)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.ACTION_CARD_PLAY, Hook.MANEUVER),
        source=__name__,
    )
)
