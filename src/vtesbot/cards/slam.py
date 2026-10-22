"""Slam (Combat). krcg id 101798.

Card text (verbatim, via the installed `krcg` 5.14+ package's own
`krcg.vtes.VTES["Slam"].card_text`, 2026-10-12, matching the raw snapshot
saved to `data/cards/101798.json` byte-for-byte, cross-checked live against
`https://api.krcg.org/card/101798`):
    "[pot] Strike: hand strike at +2 damage.
    [POT] As above, with 1 optional maneuver, only usable to get to close
    range."

Rulings (verbatim, via krcg; both the installed package and the live API
agree):
    - "Additional damage inherits all of the properties of the base
      damage." [TOM 19960225]
    - "[POT]The optional maneuver cannot be used if the strike cannot be
      used (eg. {Hidden Lurker})." [LSJ 20021028]

Card type: Combat (`types == ["Combat"]`). `discipline_requirement ==
{"type": "Mono", "disciplines": ["pot"]}` -- a single discipline, Potence,
printed at two different levels (Rulebook §3 "Discipline symbol within a
diamond ... may opt to use either the basic (plain text) or the superior
(bold) effect ... but not both"). `clan_requirement == []`, `path_
requirement == []`, `cost == {"type": "Blood", "value": 1}` -- 1 blood,
printed cost box, independent of which clause is used (same precondition
shape as Fleetness's 1-blood cost). Unlike an Action card (Rulebook §4 "If
unblocked -> pay cost, resolve. If blocked -> ... cost not paid"), a Combat
card has no block-attempt window of its own -- it is chosen as a strike or
a maneuver during an already-resolving combat -- so the 1 blood is burned
immediately as part of playing the card, not deferred to a later
resolution step. `burn_option is False`, `trifle is False`. Legal since
2007-10-26; confirmed on the active 2P allowed list (`data/formats/2p/
2026-10-03.json`, krcg id 101798).

No Ⓓ marker, no prey/predator/"other Methuselahs" wording, no political
vote -- a plain Combat card played during an already-resolving combat, so
OQ-1 (CLAUDE.md §3) does not apply.

Status: implemented. Previously `blocked` (OQ-28, `docs/OPEN_QUESTIONS.md`,
now resolved) for want of a way to let a `MANEUVER_HOOK` grant pre-commit a
combatant's strike choice for the round. `rules-engineer`'s fix:
`engine/combat.py` gained `commit_strike_for_round(context, strike)` /
`strike_committed_this_round(context)`, backed by a new `COMMITTED_STRIKE_
KEY` entry in the shared, round-scoped `round_state` dict, and `_ask_strike`
now pops and resolves any such commitment directly for that combatant's
*initial* strike of the round only (an Additional Strikes pair is
unaffected -- Rulebook §4 Combat > Additional Strikes' own "any strike can
be chosen, even if a maneuver of a strike card or a weapon has been used"
sentence). See that module's own "Maneuver bundled with a strike" docstring
section for the full mechanism, proven generically (not Slam-specific) by
its own engine-level tests; this module is the first production card wired
against it.

"[pot] Strike: hand strike at +2 damage." (basic clause): same shape as
Dust Up's own `[pot]` clause (identical printed text) -- a plain
`COMBAT_STRIKE_OPTION_HOOK` grant, gated on basic-or-superior `"pot"`, the
card in hand, and at least 1 blood on the acting vampire. "+2 damage" is
computed relative to whatever a plain hand strike would otherwise deal
right now, the same non-hardcoded computation as `dust_up.py`'s
`_base_hand_strike_damage`, so the "[TOM 19960225]" ruling (additional
damage stacks with, rather than replaces, any other strength bonus) holds
structurally. No `ignore_dodge` flag: an ordinary, dodgeable strike.

"[POT] As above, with 1 optional maneuver, only usable to get to close
range." (superior clause): a `MANEUVER_HOOK` provider, gated on superior
`"POT"`, the card in hand, at least 1 blood, and
`not strike_committed_this_round(context)` (Rulebook §4 Combat > Determine
Range: "they cannot use a second strike card or weapon to maneuver again in
the same round", enforced at this provider's own gate). "Only usable to get
to close range": gated on `state.combat_range == LONG_RANGE`, since
`_ask_maneuver` flips whichever direction the round is at regardless of the
maneuver's source -- offering this only while at long range guarantees the
flip is always long -> close. Choosing it plays the maneuver (consumes the
card, burns 1 blood, flips the range) and calls `commit_strike_for_round`
with a `HookOption` wrapping the "as above" bundled strike (identical
effect to the basic clause); per that function's contract, the wrapped
`apply(state)` has no further side effect of its own -- it exists solely
to compute and return the strike's damage from whatever base hand-strike
damage is live when the strike step actually resolves (which may differ
from the value at maneuver time).

"[POT]The optional maneuver cannot be used if the strike cannot be used
(eg. {Hidden Lurker})." [LSJ 20021028]: Hidden Lurker is not implemented in
this project, and no mechanism in this engine currently makes a combatant's
strike "unusable" (every combatant can always choose a plain hand strike at
minimum) -- vacuously always satisfied today, same "not reachable today,
but correctly modeled either way" status as `dust_up.py`'s OQ-21 citation
for Daring the Dawn. A future pass implementing such an effect will need
its own "can this combatant currently choose a strike" hook.

"with 1 optional maneuver": optional, unlike Pursuit's unqualified basic
"[cel] Maneuver." clause, but with no engine consequence beyond the
generic "do not maneuver" decline (`hooks.PASS_VALUE`, always offered
alongside any `MANEUVER_HOOK` option) -- same reasoning `pursuit.py`'s
docstring gives for its own basic clause, the inverse case.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.combat import (
    COMBAT_STATE_CONTEXT_KEY,
    COMBAT_STRIKE_OPTION_HOOK,
    LONG_RANGE,
    MANEUVER_HOOK,
    StrikeDamage,
    commit_strike_for_round,
    hand_strike_strength,
    strike_committed_this_round,
)
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101798
POT_BASIC = "pot"
POT_SUPERIOR = "POT"
BLOOD_COST = 1
STRIKE_BONUS = 2
CARD_TYPE = "Combat"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): matches
this module's own "Card type: Combat" docstring fact above -- set on both
outer options (the card actually being played), never on the nested,
already-paid-for `strike_option` wrapper `commit_strike_for_round` defers to
strike-resolution time (that one leaves `played_card_type` at its default
`None`, per that field's own docstring: it is not a fresh "play" event)."""


def _controllers_vampire(state: GameState, context: Mapping[str, Any]) -> VampireInPlay | None:
    """The vampire whose own strike/maneuver choice this hook offer is for --
    `context["player"]` is always that vampire's own controller (see
    `engine/combat.py::_ask_strike`/`_ask_maneuver` call sites: `hooks.offer(
    HOOK, state, player=player, vampire=vampire.instance_id, opponent=
    opponent.instance_id, ...)`)."""
    return state.players[context["player"]].vampires.get(context["vampire"])


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _base_hand_strike_damage(state: GameState, context: Mapping[str, Any]) -> int:
    """The damage a plain hand strike would deal right now (`engine/
    combat.py::hand_strike_strength`'s own shared computation, also used by
    `_strike_strength` internally): base strength plus any live
    `combat_strength_modifier` contribution, including a whole-combat-
    duration bonus recorded in `combat_state` (OQ-60; now threaded into
    this hook's own context by `engine/combat.py::_ask_strike`) -- so this
    card's own "+2 damage" stacks with, rather than replaces, any other
    strength bonus already in play, per "[a]dditional damage inherits all
    of the properties of the base damage" [TOM 19960225]."""
    return hand_strike_strength(
        state,
        context["player"],
        context["vampire"],
        context["opponent"],
        context.get(COMBAT_STATE_CONTEXT_KEY),
    )


def _provide_basic(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[pot] Strike: hand strike at +2 damage." -- see module docstring for
    the base-damage computation and the 1-blood printed cost."""
    vampire = _controllers_vampire(state, context)
    if vampire is None:
        return []
    disciplines = vampire.card.disciplines
    if POT_BASIC not in disciplines and POT_SUPERIOR not in disciplines:
        return []
    player = context["player"]
    if not _has_card_in_hand(state, player):
        return []
    if vampire.blood < BLOOD_COST:
        return []  # printed blood cost: must have enough blood to play at all.
    base = _base_hand_strike_damage(state, context)

    def _apply(s: GameState) -> StrikeDamage:
        play_from_hand(s, player, KRCG_ID)
        vampire.blood -= BLOOD_COST
        return StrikeDamage(amount=base + STRIKE_BONUS, ignore_dodge=False)

    return [
        HookOption(
            choice=Choice("slam:basic", "Slam [pot]: hand strike +2 damage"),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


def _provide_superior_maneuver(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[POT] As above, with 1 optional maneuver, only usable to get to
    close range." -- see module docstring for the strike-commitment, the
    "only usable to get to close range" gate, and the 1-blood printed
    cost."""
    vampire = _controllers_vampire(state, context)
    if vampire is None:
        return []
    if POT_SUPERIOR not in vampire.card.disciplines:
        return []
    player = context["player"]
    if not _has_card_in_hand(state, player):
        return []
    if vampire.blood < BLOOD_COST:
        return []  # printed blood cost: must have enough blood to play at all.
    if strike_committed_this_round(context):
        return []  # "cannot use a second strike card or weapon to maneuver again" (OQ-28).
    if state.combat_range != LONG_RANGE:
        return []  # "only usable to get to close range": only offered while at long range.

    def _apply(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        vampire.blood -= BLOOD_COST

        def _strike_apply(s2: GameState) -> StrikeDamage:
            # Invoked later, at strike-resolution time (commit_strike_for_
            # round's own contract) -- no further side effect: the card was
            # already played, and its cost already paid, above.
            base = _base_hand_strike_damage(s2, context)
            return StrikeDamage(amount=base + STRIKE_BONUS, ignore_dodge=False)

        strike_option = HookOption(
            choice=Choice("slam:superior_strike", "Slam [POT]: hand strike +2 damage (committed)"),
            apply=_strike_apply,
        )
        commit_strike_for_round(context, strike_option)

    return [
        HookOption(
            choice=Choice(
                "slam:superior_maneuver",
                "Slam [POT]: maneuver to close range, with hand strike +2 damage",
            ),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


hooks.register(COMBAT_STRIKE_OPTION_HOOK, _provide_basic)
hooks.register(MANEUVER_HOOK, _provide_superior_maneuver)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Slam",
        status=Status.IMPLEMENTED,
        hooks=(Hook.COMBAT_STRIKE_OPTION, Hook.MANEUVER),
        source=__name__,
    )
)
