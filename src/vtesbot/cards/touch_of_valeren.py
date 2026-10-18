"""Touch of Valeren (Action/Combat). krcg id 102262.

Card text (verbatim, via `krcg.load()` + `msgspec.json.encode()`, project's
`uv run` venv (krcg 5.14), 2026-10-18, matching the raw snapshot
`data/cards/102262.json`):
    "[for] [ACTION] +1 stealth action. Add 3 blood or life to a minion, not
    to exceed their starting life.
    [for] [COMBAT] Prevent all damage from the opposing minion's strike.
    [FOR] [COMBAT] Only usable by a ready vampire not involved in the combat
    involving another minion you control. Prevent all damage to that minion
    from the opposing minion's strike."

Ruling (verbatim, via krcg): "[COMBAT]Cannot be used if there is no damage
to prevent. [LSJ 20001114]" -- scoped to both Combat clauses (the Action
clause is not a damage-prevention effect at all).

Card type: dual Action/Combat (`types == ["Action", "Combat"]`), one
physical card playable as either depending on when it is used, never both
on the same play -- the first card in this pool whose two clauses carry
genuinely different printed types (every other multi-clause card so far
splits basic/superior within one type, e.g. `bonding.py`).
`HookOption.played_card_type` is set per-clause to whichever printed type
that clause actually is; nothing downstream looks up a type by `krcg_id` --
it is only ever read off the specific chosen option (`engine/hooks.py::
mark_reaction_played`/`offer_cancel_as_played`) -- so no engine change is
needed for a card with two printed types.

`clan_requirement == ["Salubri"]`: gates the *playing* vampire on every
clause (Rulebook §2 "Requirements for Playing Cards"), including the
superior Combat clause's assisting vampire -- not the minion being
protected. `discipline_requirement == {"type": "Mono", "disciplines":
["for"]}`: basic Fortitude to play any clause; superior Fortitude ("FOR")
additionally required for the bracketed `[FOR]` clause (Rulebook §3). `cost
== {"type": "Blood", "value": 1}`: a genuine printed blood-cost box,
independent of which clause is used -- same "paid by the playing vampire,
checked at offer time, charged in full" shape as `slam.py`/`fleetness.py`.
The Action clause pays it inside `resolve()`, only on the unblocked branch
(Rulebook §4 step 3: "cost not paid" if blocked); both Combat clauses pay it
immediately in `apply()`, since a Combat card has no block-attempt window of
its own (`slam.py`'s own precedent). `burn_option is False`, `trifle is
False`. Legal since 2024-01-31; on the active 2P allowed list and in
`data/decks/vekn-2p/salubri.json` (2 copies).

"[for] [ACTION] +1 stealth action. Add 3 blood or life to a minion, not to
exceed their starting life.": no printed Ⓓ marker. Rulebook §8 Glossary:
"Directed Action: An action ... that targets one or more other Methuselahs,
or the minions or cards they control." / "Undirected Action: An action that
is not directed." -- an undirected action can therefore never resolve
against another Methuselah's own minion; `aniel.py`'s own docstring already
applies the converse of this same rule (its printed Ⓓ marker is what settles
that its bare "another ready minion" must be the *opponent's*). So "a
minion" here, despite carrying no "you control" qualifier in the printed
text, reads as "a minion you control" -- a direct, symmetric consequence of
the glossary definition already relied on elsewhere in this pool, not a
guess. Mirrors `seraphina.py`'s nearly identical "add 2 blood or life to a
minion you control ... not to exceed starting life" (krcg 201686, OQ-61):
one option per eligible controlled vampire (`zone in ("ready", "torpor")`)
or ready, uncontested ally, blood capped via `engine/damage.py::add_blood`
(OQ-8) or life capped via `engine/allies.py::add_life` (OQ-61) -- "3"
replaces Seraphina's "2", otherwise identical shape, including the
self-targeting case (the acting vampire is never excluded as a target).
"+1 stealth action" bare: undirected, baseline stealth 1 (`RECRUIT_ALLY_
STEALTH`/`seraphina.py` convention). Wired against `ACTION_CARD_PLAY_HOOK`;
`remove_from_hand` + `ActionCardSpec.name=NAME` per OQ-57 Finding 1/2 (the
generic "same named action card once per turn" cap, reused even though this
card prints only one Action-mode clause).

"[for] [COMBAT] Prevent all damage from the opposing minion's strike.":
self-targeted, single-strike (not "this round", unlike `rolling_with_the_
punches.py`'s own superior clause) full prevention -- reuses that module's
own `_prevent_all` shape (zeroes both `normal` and `aggravated`) with no
`mark_mandatory_full_prevention_active` persistence, since the text covers
only the one strike already in flight. Gated like `opikun.py`'s own
identical "from the opposing minion's strike" wording: `combat_state is not
None` (this damage really is strike damage from an active combat, OQ-60) and
some damage present [LSJ 20001114]. Played by the damaged vampire itself
(`context["vampire"]`), basic-or-superior Fortitude.

"[FOR] [COMBAT] Only usable by a ready vampire not involved in the combat
involving another minion you control. Prevent all damage to that minion
from the opposing minion's strike.": the superior clause's "playing vampire
!= protected vampire" shape has direct precedent in this pool --
`opikun.py`'s own crypt ability already lets a *different* vampire (Opikun,
found independently among `player`'s own vampires) act on the vampire
actually named by `context["vampire"]`, and `organized_resistance.py`'s "An
Anarch you control gets +1 intercept" already lets a *different* playing
vampire (the Baron) affect a named recipient that is not itself.
`DAMAGE_PREVENTION_HOOK` is a single-sided window offered only to the
damaged vampire's own controller (`apply_damage`'s own `player` argument),
so "another minion you control" is exactly `context["vampire"]` (always
that same controller's own minion), and "a ready vampire not involved in
the combat" is any *other* ready vampire of that same controller's --
combat is always exactly one vampire per side (Rulebook §8 Glossary
"Combatant"/"Opposing minion": "the other one", singular; confirmed by
`engine/combat.py::run_combat`'s own call-site structure, a single
`acting_vampire`/`blocking_vampire` pair, not a list of combatants per
side), so the only one of `player`'s own vampires ever "involved in the
combat" at this dispatch point is `context["vampire"]` itself. No new
engine primitive is needed:
this reads off the existing `DAMAGE_PREVENTION_HOOK` context exactly as
`opikun.py`/`organized_resistance.py` already do -- both fully implemented,
not gated behind an Open Question. Candidate gates: `zone == "ready"`, clan
Salubri, superior `"FOR"`, the card in hand, and enough blood for the
printed cost -- paid by the candidate (the vampire actually playing the
card), never the protected one (Rulebook §2 "costs are paid from own
resources only").
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand, remove_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.allies import add_life
from vtesbot.engine.attachments import effective_capacity
from vtesbot.engine.damage import COMBAT_STATE_CONTEXT_KEY, DAMAGE_PREVENTION_HOOK, add_blood
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import (
    ACTION_CARD_PLAY_HOOK,
    ActionCardSpec,
    action_card_already_played_this_turn,
)
from vtesbot.engine.state import AllyInPlay, GameState, VampireInPlay

KRCG_ID = 102262
NAME = "Touch of Valeren"
CLAN = "Salubri"
BASIC = "for"
SUPERIOR = "FOR"
BLOOD_COST = 1
"""Printed blood-cost box, independent of which clause is used (module
docstring)."""
ACTION_STEALTH = 1
"""Verbatim "+1 stealth action" (bare): undirected, baseline 1."""
ADD_AMOUNT = 3
"""Verbatim "Add 3 blood or life"."""
ACTION_CARD_TYPE = "Action"
COMBAT_CARD_TYPE = "Combat"
"""`HookOption.played_card_type` per clause (module docstring): this
physical card prints two different types, set here to whichever one each
clause actually is."""

VAMPIRE_IN_PLAY_ZONES = ("ready", "torpor")
ALLY_IN_PLAY_ZONES = ("ready",)


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _controlled_vampires_in_play(state: GameState, player: str) -> list[VampireInPlay]:
    return [
        v for v in state.players[player].vampires.values() if v.zone in VAMPIRE_IN_PLAY_ZONES
    ]


def _controlled_allies_in_play(state: GameState, player: str) -> list[AllyInPlay]:
    return [a for a in state.players[player].allies.values() if a.zone in ALLY_IN_PLAY_ZONES]


def _prevent_all(damage_box: dict[str, int]) -> None:
    """ "Prevent all damage from the opposing minion's strike" -- zeroes
    both `"normal"` and `"aggravated"` (mirrors `rolling_with_the_punches.
    py`'s own `_prevent_all`), scoped to this one strike only (module
    docstring)."""
    damage_box["normal"] = 0
    damage_box["aggravated"] = 0


# --- "[for] [ACTION] +1 stealth action. Add 3 blood or life to a minion,
#     not to exceed their starting life." -----------------------------------


def _vampire_option(
    player: str, acting_vampire: VampireInPlay, target: VampireInPlay
) -> HookOption:
    label = f"Touch of Valeren [for]: add 3 blood to {target.card.name}"

    def _apply(s: GameState) -> ActionCardSpec:
        remove_from_hand(s, player, KRCG_ID)

        def resolve(pending: dict[str, Any]) -> None:
            del pending  # no later hook window of its own to feed.
            acting_vampire.blood -= BLOOD_COST  # paid now: action resolved unblocked.
            add_blood(s, target, ADD_AMOUNT)

        return ActionCardSpec(
            base_stealth=ACTION_STEALTH, directed=False, resolve=resolve, name=NAME
        )

    return HookOption(
        choice=Choice(f"touch_of_valeren:action:blood:{target.instance_id}", label),
        apply=_apply,
        played_card_type=ACTION_CARD_TYPE,
    )


def _ally_option(player: str, acting_vampire: VampireInPlay, ally: AllyInPlay) -> HookOption:
    label = f"Touch of Valeren [for]: add 3 life to {ally.name}"

    def _apply(s: GameState) -> ActionCardSpec:
        remove_from_hand(s, player, KRCG_ID)

        def resolve(pending: dict[str, Any]) -> None:
            del pending
            acting_vampire.blood -= BLOOD_COST
            add_life(ally, ADD_AMOUNT)

        return ActionCardSpec(
            base_stealth=ACTION_STEALTH, directed=False, resolve=resolve, name=NAME
        )

    return HookOption(
        choice=Choice(f"touch_of_valeren:action:life:{ally.instance_id}", label),
        apply=_apply,
        played_card_type=ACTION_CARD_TYPE,
    )


def _provide_touch_of_valeren_action(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    player = context["player"]
    acting_vampire = state.players[player].vampires.get(context["vampire"])
    if acting_vampire is None:
        return []
    if acting_vampire.card.clan != CLAN:
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

    options: list[HookOption] = []
    for vampire in _controlled_vampires_in_play(state, player):
        if effective_capacity(state, vampire) - vampire.blood <= 0:
            continue
        options.append(_vampire_option(player, acting_vampire, vampire))
    for ally in _controlled_allies_in_play(state, player):
        if ally.starting_life - ally.life <= 0:
            continue
        options.append(_ally_option(player, acting_vampire, ally))
    return options


# --- "[for] [COMBAT] Prevent all damage from the opposing minion's
#     strike." ---------------------------------------------------------------


def _provide_touch_of_valeren_self(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    player = context["player"]
    combat_state = context.get(COMBAT_STATE_CONTEXT_KEY)
    if combat_state is None:
        return []  # not strike damage from an active combat (module docstring).
    damage_box = context["damage"]
    if damage_box.get("normal", 0) <= 0 and damage_box.get("aggravated", 0) <= 0:
        return []  # "Cannot be used if there is no damage to prevent." [LSJ 20001114]
    vampire = state.players[player].vampires.get(context["vampire"])
    if vampire is None:
        return []
    if vampire.card.clan != CLAN:
        return []
    disciplines = vampire.card.disciplines
    if BASIC not in disciplines and SUPERIOR not in disciplines:
        return []
    if not _has_card_in_hand(state, player):
        return []
    if vampire.blood < BLOOD_COST:
        return []  # printed blood cost.

    def _apply(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        vampire.blood -= BLOOD_COST
        _prevent_all(damage_box)

    return [
        HookOption(
            choice=Choice(
                "touch_of_valeren:combat:self",
                f"Touch of Valeren [for]: prevent all damage to {vampire.card.name} "
                "from the opposing minion's strike",
            ),
            apply=_apply,
            played_card_type=COMBAT_CARD_TYPE,
        )
    ]


# --- "[FOR] [COMBAT] Only usable by a ready vampire not involved in the
#     combat involving another minion you control. Prevent all damage to
#     that minion from the opposing minion's strike." -----------------------


def _provide_touch_of_valeren_assist(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    player = context["player"]
    combat_state = context.get(COMBAT_STATE_CONTEXT_KEY)
    if combat_state is None:
        return []
    damage_box = context["damage"]
    if damage_box.get("normal", 0) <= 0 and damage_box.get("aggravated", 0) <= 0:
        return []  # "Cannot be used if there is no damage to prevent." [LSJ 20001114]
    protected = state.players[player].vampires.get(context["vampire"])
    if protected is None:
        return []
    if not _has_card_in_hand(state, player):
        return []

    options: list[HookOption] = []
    for candidate in state.players[player].vampires.values():
        if candidate.instance_id == protected.instance_id:
            continue  # "not involved in the combat" -- see module docstring.
        if candidate.zone != "ready":
            continue
        if candidate.card.clan != CLAN:
            continue
        if SUPERIOR not in candidate.card.disciplines:
            continue
        if candidate.blood < BLOOD_COST:
            continue  # printed blood cost, paid by the playing (candidate) vampire.

        def _apply(s: GameState, candidate: VampireInPlay = candidate) -> None:
            play_from_hand(s, player, KRCG_ID)
            candidate.blood -= BLOOD_COST
            _prevent_all(damage_box)

        options.append(
            HookOption(
                choice=Choice(
                    f"touch_of_valeren:combat:assist:{candidate.instance_id}",
                    f"Touch of Valeren [FOR]: {candidate.card.name} prevents all damage to "
                    f"{protected.card.name} from the opposing minion's strike",
                ),
                apply=_apply,
                played_card_type=COMBAT_CARD_TYPE,
            )
        )
    return options


hooks.register(ACTION_CARD_PLAY_HOOK, _provide_touch_of_valeren_action)
hooks.register(DAMAGE_PREVENTION_HOOK, _provide_touch_of_valeren_self)
hooks.register(DAMAGE_PREVENTION_HOOK, _provide_touch_of_valeren_assist)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.ACTION_CARD_PLAY, Hook.DAMAGE_PREVENTION),
        source=__name__,
    )
)
