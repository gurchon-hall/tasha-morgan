"""Rolling with the Punches (Combat). krcg id 101649.

Card text (verbatim, via the installed `krcg` 4.18 `krcg.vtes.VTES` package
-- 2026-10-15, matching the raw snapshot saved to `data/cards/101649.json`):
    "[for] Prevent 1 damage.
    [FOR] Burn 1 blood to prevent all damage from the opposing minion's
    strikes this round."

Rulings (verbatim, via krcg; `VTES["Rolling with the Punches"].rulings`):
    - "[FOR]The burn blood effect is not reduced by effects that reduce
      the cost of the card (eg. {Adana de Sforza}). [ANK 20210226]"
    - "[FOR]The card cannot be played if the minion cannot afford to burn
      the blood. [ANK 20210226]"
    - "Cannot be used if there is no damage to prevent. [LSJ 20001114]"

Card type: Combat (`types == ["Combat"]`). `discipline_requirement ==
{"type": "Mono", "disciplines": ["for"]}`. `blood_cost`/`pool_cost` are
both `None` -- the card itself is free; the superior clause's "Burn 1
blood" is an in-text effect cost, not a printed cost box (same shape as
the two ANK 20210226 rulings above, which both talk about "the burn blood
effect", not a cost to play the card at all). Legal since 1996-10-28;
confirmed on the active 2P allowed list (`data/formats/2p/
2026-10-03.json`, krcg id 101649) and in `data/decks/vekn-2p/
ventrue.json`.

Status: implemented (ENG-036, resolved). Both
clauses are wired against the already-wired `DAMAGE_PREVENTION_HOOK`
(`engine/damage.py::apply_damage`'s "Prevent step"), offered together
whenever eligible (Rulebook §3 "may opt to use either effect"):

- `[for]`: gated on basic-or-superior `"for"`/`"FOR"`, the card in hand,
  and some preventable damage present [LSJ 20001114] -- reduces whichever
  damage type (normal or aggravated; the text has no "non-aggravated"
  qualifier, unlike Soak) is actually present by 1 point.
  `apply_damage`'s only production call site
  (`engine/combat.py::_resolve_strike_pair`) always passes a single
  damage type per call, so both types being simultaneously positive here
  would be an engine invariant violation, not a legal game state --
  surfaced loudly (`AssertionError`), never silently resolved one way or
  the other.
- `[FOR]`: additionally gated on superior `"FOR"` and `vampire.blood >= 1`
  [ANK 20210226] ("cannot be played if the minion cannot afford to burn
  the blood"). Its `apply` burns 1 blood directly (`vampire.blood -= 1`);
  per the other ANK 20210226 ruling this specific burn is NOT reduced by
  any cost-reduction mechanism (this codebase has none that would
  otherwise reach it today, but none must ever be routed in here).
  `apply` also zeroes the *current* strike's own `damage_box` -- the
  text's "prevent all damage from the opposing minion's strikes this
  round" carries no carve-out for the triggering strike -- and calls
  `engine/damage.py::mark_mandatory_full_prevention_active` so every
  later `apply_damage` call this round against this vampire is
  automatically and fully prevented with no further decision asked
  (`MANDATORY_FULL_PREVENTION_KEY`, the primitive ENG-036 added to resolve
  this card's own remaining gap). `round_state` is read from
  `DAMAGE_PREVENTION_HOOK`'s own context (`ROUND_STATE_CONTEXT_KEY`),
  which also implicitly identifies "the opposing minion" -- one
  `run_combat` call is always exactly one 1-on-1 combat.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.attachments import effective_disciplines
from vtesbot.engine.damage import (
    DAMAGE_PREVENTION_HOOK,
    ROUND_STATE_CONTEXT_KEY,
    mark_mandatory_full_prevention_active,
)
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 101649
NAME = "Rolling with the Punches"
BASIC = "for"
SUPERIOR = "FOR"
CARD_TYPE = "Combat"
"""`HookOption.played_card_type` (ENG-023): matches
this module's own "Card type: Combat" docstring fact above."""


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _prevent_one_point(damage_box: dict[str, int]) -> None:
    """ "Prevent 1 damage" -- see module docstring for why `normal` and
    `aggravated` being simultaneously positive here is an engine invariant
    violation rather than a ruling ambiguity to resolve."""
    normal = damage_box.get("normal", 0)
    aggravated = damage_box.get("aggravated", 0)
    if normal > 0 and aggravated > 0:
        raise AssertionError(
            "rolling_with_the_punches: damage_box has both normal and aggravated "
            "damage at once, which no production call site produces today "
            "(engine invariant violation, not a legal game state)"
        )
    if aggravated > 0:
        damage_box["aggravated"] = aggravated - 1
    elif normal > 0:
        damage_box["normal"] = normal - 1


def _prevent_all(damage_box: dict[str, int]) -> None:
    """ "[FOR] ... prevent all damage from the opposing minion's strikes
    this round" -- zeroes the *current* strike's damage; the rest of the
    round is covered separately by `mark_mandatory_full_prevention_active`
    (see module docstring)."""
    damage_box["normal"] = 0
    damage_box["aggravated"] = 0


def _provide_prevent(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[for] Prevent 1 damage." and "[FOR] Burn 1 blood to prevent all
    damage from the opposing minion's strikes this round." -- see module
    docstring for each clause's own gates."""
    player = context["player"]
    vampire = state.players[player].vampires.get(context["vampire"])
    if vampire is None:
        return []
    disciplines = effective_disciplines(state, vampire)
    if BASIC not in disciplines and SUPERIOR not in disciplines:
        return []
    if not _has_card_in_hand(state, player):
        return []
    damage_box = context["damage"]
    if damage_box.get("normal", 0) <= 0 and damage_box.get("aggravated", 0) <= 0:
        return []  # "Cannot be used if there is no damage to prevent." [LSJ 20001114]

    options: list[HookOption] = []

    def _apply_basic(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        _prevent_one_point(damage_box)

    options.append(
        HookOption(
            choice=Choice(
                "rolling_with_the_punches:basic", "Rolling with the Punches [for]: prevent 1 damage"
            ),
            apply=_apply_basic,
            played_card_type=CARD_TYPE,
        )
    )

    if SUPERIOR in disciplines and vampire.blood >= 1:
        round_state = context.get(ROUND_STATE_CONTEXT_KEY)
        vampire_id = vampire.instance_id

        def _apply_superior(s: GameState) -> None:
            play_from_hand(s, player, KRCG_ID)
            vampire.blood -= 1  # [ANK 20210226]: never reduced by a cost-reducer.
            _prevent_all(damage_box)
            mark_mandatory_full_prevention_active(round_state, vampire_id)

        options.append(
            HookOption(
                choice=Choice(
                    "rolling_with_the_punches:superior",
                    "Rolling with the Punches [FOR]: burn 1 blood, prevent all damage this round",
                ),
                apply=_apply_superior,
                played_card_type=CARD_TYPE,
            )
        )

    return options


hooks.register(DAMAGE_PREVENTION_HOOK, _provide_prevent)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.DAMAGE_PREVENTION,),
        source=__name__,
    )
)
