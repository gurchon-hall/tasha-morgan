"""Soak (Combat). krcg id 101817.

Card text (verbatim, via the installed `krcg` 4.18 `krcg.vtes.VTES`
package, 2026-10-15, matching the raw snapshot saved to
`data/cards/101817.json`):
    "A vampire can play only one Soak each round.
    [for] Prevent 2 non-aggravated damage.
    [FOR] Prevent 4 non-aggravated damage."

Rulings (via krcg; `VTES["Soak"].rulings`):
    - Cannot prevent aggravated damage, even if the minion treats it as
      normal damage (e.g. Skin of Night). [LSJ 20040812-2] [PIB 20130327]
    - Preventing more than the damage actually being resolved still
      prevents all of it. [RTR 20041202]
    - Unused prevention points don't carry over (not a "can/may
      prevent" effect). [ANK 20200318] [LSJ 20001114]
    - Cannot be used if there is no damage to prevent. [LSJ 20001114]

Card type: Combat (`types == ["Combat"]`). `disciplines == ["for"]`:
basic Fortitude for the `[for]` clause, superior for `[FOR]`. No
blood/pool cost. Legal since 2004-05-17; confirmed on the active 2P
allowed list (`data/formats/2p/2026-10-03.json`) and in
`data/decks/vekn-2p/ventrue.json`.

Status: implemented. Previously `blocked` (ENG-036, now resolved):
`engine/damage.py::apply_damage`'s Prevent step now threads
`ROUND_STATE_CONTEXT_KEY: round_state` into `DAMAGE_PREVENTION_HOOK`'s
context, so a provider can read/write a round-scoped flag the same way
`engine/combat.py::additional_strike_limit_used`/
`mark_additional_strike_limit_used` already do for
`ADDITIONAL_STRIKE_LIMIT_KEY` -- used here for "A vampire can play only
one Soak each round" (`_SOAK_USED_KEY`, `dict[str, bool]` per vampire
id). Missing `round_state` degrades to "not used" (same convention as
every other round-scoped cap in this codebase), so the cap is simply
unenforced if this hook is ever offered outside a combat round.

Both discipline levels are offered as separate options whenever
eligible rather than only the higher one, per the Rulebook §3 "may opt
to use either the basic ... or the superior ... effect" rule already
cited in `slam.py`'s own docstring: a vampire with superior Fortitude
sees both the `[for]` and `[FOR]` options. Each `apply` plays the card,
marks the round-scoped cap, and reduces `damage_box["normal"]` only
(never `"aggravated"`) by `min(printed_amount, damage_box["normal"])`
-- naturally satisfies "prevents more than resolved still prevents all
of it" [RTR 20041202] with no overflow bookkeeping, and "no carryover"
[ANK 20200318] [LSJ 20001114] since no leftover is ever stored. The
"no damage to prevent" gate [LSJ 20001114] and the "cannot prevent
aggravated" restriction [LSJ 20040812-2] [PIB 20130327] both fold into
gating on, and only ever touching, `damage_box["normal"]`.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.damage import DAMAGE_PREVENTION_HOOK, ROUND_STATE_CONTEXT_KEY
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 101817
NAME = "Soak"
BASIC = "for"
SUPERIOR = "FOR"
BASIC_PREVENT = 2
SUPERIOR_PREVENT = 4
CARD_TYPE = "Combat"
"""`HookOption.played_card_type` (ENG-023): matches
this module's own "Card type: Combat" docstring fact above."""

_SOAK_USED_KEY = "soak_used"
"""Key inside `round_state` for "A vampire can play only one Soak each
round", a `dict[str, bool]` keyed per vampire id (mirrors
`engine/combat.py::ADDITIONAL_STRIKE_LIMIT_KEY`'s own shape)."""


def _soak_used_this_round(context: Mapping[str, Any]) -> bool:
    """Whether `context["vampire"]` already played a Soak this round.
    Missing `round_state` degrades to False (see module docstring)."""
    round_state = context.get(ROUND_STATE_CONTEXT_KEY)
    if round_state is None:
        return False
    return bool(round_state.get(_SOAK_USED_KEY, {}).get(context["vampire"]))


def _mark_soak_used(context: Mapping[str, Any]) -> None:
    """Record that `context["vampire"]` played a Soak this round; see
    `_soak_used_this_round`. Missing `round_state` is a no-op."""
    round_state = context.get(ROUND_STATE_CONTEXT_KEY)
    if round_state is not None:
        round_state.setdefault(_SOAK_USED_KEY, {})[context["vampire"]] = True


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _prevent_non_aggravated(damage_box: dict[str, int], amount: int) -> None:
    """Reduce `damage_box["normal"]` by `min(amount, damage_box["normal"])`;
    never touches `"aggravated"` [LSJ 20040812-2] [PIB 20130327]."""
    normal = damage_box.get("normal", 0)
    damage_box["normal"] = normal - min(amount, normal)


def _provide_soak(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """Both "[for] Prevent 2 non-aggravated damage." and "[FOR] Prevent 4
    non-aggravated damage." -- see module docstring for the once-per-round
    cap and the basic/superior "either effect" choice."""
    player = context["player"]
    vampire = state.players[player].vampires.get(context["vampire"])
    if vampire is None:
        return []
    if _soak_used_this_round(context):
        return []  # "A vampire can play only one Soak each round."
    if not _has_card_in_hand(state, player):
        return []
    damage_box = context["damage"]
    if damage_box.get("normal", 0) <= 0:
        return []  # "Cannot be used if there is no damage to prevent." [LSJ 20001114]

    disciplines = vampire.card.disciplines
    options: list[HookOption] = []

    def _apply_basic(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        _mark_soak_used(context)
        _prevent_non_aggravated(damage_box, BASIC_PREVENT)

    def _apply_superior(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        _mark_soak_used(context)
        _prevent_non_aggravated(damage_box, SUPERIOR_PREVENT)

    if BASIC in disciplines or SUPERIOR in disciplines:
        options.append(
            HookOption(
                choice=Choice("soak:basic", "Soak [for]: prevent 2 non-aggravated damage"),
                apply=_apply_basic,
                played_card_type=CARD_TYPE,
            )
        )
    if SUPERIOR in disciplines:
        options.append(
            HookOption(
                choice=Choice("soak:superior", "Soak [FOR]: prevent 4 non-aggravated damage"),
                apply=_apply_superior,
                played_card_type=CARD_TYPE,
            )
        )
    return options


hooks.register(DAMAGE_PREVENTION_HOOK, _provide_soak)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.DAMAGE_PREVENTION,),
        source=__name__,
    )
)
