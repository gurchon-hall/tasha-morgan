"""Maila (Vampire). krcg 201633. Snapshot: data/cards/201633.json
Once per turn [ANK 20230122]; any action, not only bleeds. The stealth window
only opens on the acting player's turn, which is "during your turn"."""

from vtesbot.cards.card import Card
from vtesbot.engine.hook_contexts import StealthModifierContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 201633
POLITICAL_ACTION_CARD_TYPE = "Political Action"
ABILITY_KEY = "maila_discard_for_stealth"

card = Card(KRCG_ID, "Maila")


def _controlled_ready_maila(state: GameState, player: str) -> VampireInPlay | None:
    for vampire in state.players[player].vampires.values():
        if vampire.card.krcg_id == KRCG_ID and vampire.zone == "ready":
            return vampire
    return None


def _discard_one_political_action_card_from_hand(state: GameState, player: str) -> None:
    """A plain discard, no replacement; which card never matters."""
    hand = state.players[player].hand
    for index, hand_card in enumerate(hand):
        if hand_card.card_type == POLITICAL_ACTION_CARD_TYPE:
            state.players[player].ash_heap.append(hand.pop(index))
            return
    raise AssertionError(
        f"{player} has no political action card left in hand to discard for Maila's "
        "+1 stealth (engine invariant violation, not a legal game state)"
    )


@card.on(Hook.STEALTH_MODIFIER)
def _provide_maila(state: GameState, ctx: StealthModifierContext) -> list[HookOption]:
    player = ctx["player"]
    maila = _controlled_ready_maila(state, player)
    if maila is None:
        return []
    if not any(c.card_type == POLITICAL_ACTION_CARD_TYPE for c in state.players[player].hand):
        return []
    if maila.ability_used_turn.get(ABILITY_KEY) == state.turn_number:
        return []

    def _apply(s: GameState) -> int:
        _discard_one_political_action_card_from_hand(s, player)
        maila.ability_used_turn[ABILITY_KEY] = s.turn_number
        return 1

    return [
        card.option(
            f"maila_discard_for_stealth:{maila.instance_id}",
            "Maila: discard a political action card to give +1 stealth",
            _apply,
        )
    ]
