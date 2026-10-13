"""Maila (crypt vampire ability). krcg id 201633.

Printed text (verbatim, via the installed `krcg` package's `krcg.load()
[201633].text`, re-verified live 2026-10-13, matching the raw snapshot
`data/cards/201633.json`): "Camarilla primogen: If Maila is ready during
your turn, you can discard a political action card [POLITICAL ACTION] to
give a minion you control +1 stealth for the current action."

Ruling (verbatim, via krcg): "Her ability can only be used once during each
of your turns. [RBK wording-templates] [ANK 20230122]." The
`[RBK wording-templates]` citation confirms this is the generic Rulebook
SS3 "Wording templates" > "During X, do Y" rule, verbatim: "only one Y can
be done per X with this card" (`data/sources/rulebook/2026-10-09/
3-playing-the-game.md` lines 86-91) -- the same mechanism Diana Iadanza's
clause 1 already uses for "once per referendum"
(`src/vtesbot/cards/diana_iadanza.py`), here scoped to a whole turn instead.

Card type: crypt vampire (`types == ["Vampire"]`). Clan Toreador, title
"Primogen", group G6, capacity 6, disciplines `["cel", "AUS", "PRE"]`.

Hook/timing: a `STEALTH_MODIFIER_HOOK` provider (`engine/action.py`), the
same hook Bonding's superior clause rides (`src/vtesbot/cards/bonding.py`)
-- `context["player"]` is always the acting Methuselah currently resisting
a block attempt while stealth is needed
(`_duel_stealth_intercept`'s "only when needed" ping-pong), which is
exactly "during your turn" for free, the same reasoning Bonding's own
docstring gives for *its* hook. Unlike Bonding's superior clause, "for the
current action" carries no restriction to bleed only, so this provider does
not gate on `context["action"]`.

Once-per-turn tracking: `VampireInPlay.ability_used_turn` (`engine/
state.py`), a new generic field added by this pass -- no existing scratch
container is turn-scoped (`pending` spans one action, `cancel_context
["pending"]` spans one referendum), so this is the minimal addition that
fits the "During X, do Y" cap when X is a turn. See that field's own
docstring for the shared mechanism; `ABILITY_KEY` below is this module's
own key into it.

Gates: Maila controlled by `context["player"]`, `zone == "ready"` (plain
ready check -- the only on-file ruling is the once-per-turn cap, nothing
about torpor, unlike Modius), at least one `"Political Action"`-type
`LibraryCard` in hand, and not already used this `GameState.turn_number`.

Effect: `apply()` discards (hand -> ash heap, no replacement drawn --
Rulebook SS8 glossary "Discard") the first Political-Action-type card found
in hand -- which card is never a meaningful choice (same reasoning as
`modius.py::_discard_one_master_card_from_hand`) -- marks the once-per-turn
flag, and returns `1` (the `STEALTH_MODIFIER_HOOK` `apply` contract: an
`int` delta added to `stealth`). `played_card_type` stays at its default
`None`: this option is Maila's own printed ability being activated, not a
card being played -- the discarded political action card is the ability's
cost, never itself played (same reasoning as `modius.py`).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import STEALTH_MODIFIER_HOOK
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 201633
POLITICAL_ACTION_CARD_TYPE = "Political Action"
ABILITY_KEY = "maila_discard_for_stealth"


def _controlled_ready_maila(state: GameState, player: str) -> VampireInPlay | None:
    for vampire in state.players[player].vampires.values():
        if vampire.card.krcg_id == KRCG_ID and vampire.zone == "ready":
            return vampire
    return None


def _has_political_action_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.card_type == POLITICAL_ACTION_CARD_TYPE for card in state.players[player].hand)


def _discard_one_political_action_card_from_hand(state: GameState, player: str) -> None:
    """Plain discard (module docstring): move one `"Political Action"`-type
    `LibraryCard` from `player`'s hand to their ash heap, no replacement
    drawn. First match in hand order, deterministically (which card is never
    a meaningful choice -- same reasoning as `modius.py`'s own helper)."""
    hand = state.players[player].hand
    for index, card in enumerate(hand):
        if card.card_type == POLITICAL_ACTION_CARD_TYPE:
            state.players[player].ash_heap.append(hand.pop(index))
            return
    raise AssertionError(
        f"{player} has no political action card left in hand to discard for Maila's "
        "+1 stealth (engine invariant violation, not a legal game state)"
    )


def _provide_maila(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    maila = _controlled_ready_maila(state, player)
    if maila is None:
        return []
    if not _has_political_action_card_in_hand(state, player):
        return []
    if maila.ability_used_turn.get(ABILITY_KEY) == state.turn_number:
        return []

    def _apply(s: GameState) -> int:
        _discard_one_political_action_card_from_hand(s, player)
        maila.ability_used_turn[ABILITY_KEY] = s.turn_number
        return 1

    return [
        HookOption(
            choice=Choice(
                f"maila_discard_for_stealth:{maila.instance_id}",
                "Maila: discard a political action card to give +1 stealth",
            ),
            apply=_apply,
            # `played_card_type` stays at its default `None` (module
            # docstring): this option is Maila's own printed ability being
            # activated, not a card being played -- the discarded card is
            # the ability's cost, never played.
        )
    ]


hooks.register(STEALTH_MODIFIER_HOOK, _provide_maila)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Maila",
        status=Status.IMPLEMENTED,
        hooks=(Hook.STEALTH_MODIFIER,),
        source=__name__,
    )
)
