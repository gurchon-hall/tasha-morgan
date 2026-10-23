"""Carmelita Neillson (Vampire). krcg 201625. Snapshot: data/cards/201625.json
"Camarilla:" gates on her current sect; "ready" means in the ready region,
locked or not (RUL-019)."""

from vtesbot.cards.card import Card
from vtesbot.engine.cards import Sect
from vtesbot.engine.hook_contexts import HandSizeModifierContext
from vtesbot.engine.hooks import Hook
from vtesbot.engine.state import GameState

KRCG_ID = 201625

card = Card(KRCG_ID, "Carmelita Neillson")


@card.on(Hook.HAND_SIZE_MODIFIER)
def _hand_size(state: GameState, ctx: HandSizeModifierContext) -> int:
    for vampire in state.players[ctx["player"]].vampires.values():
        if (
            vampire.card.krcg_id == KRCG_ID
            and vampire.zone == "ready"
            and vampire.card.sect is Sect.CAMARILLA
        ):
            return 1
    return 0
