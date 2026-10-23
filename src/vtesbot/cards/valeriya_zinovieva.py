"""Valeriya Zinovieva (Vampire). krcg 201614. Snapshot: data/cards/201614.json
"+1 strength" is her own strength only."""

from vtesbot.cards.card import Card
from vtesbot.engine.hook_contexts import CombatStrengthModifierContext
from vtesbot.engine.hooks import Hook
from vtesbot.engine.state import GameState

KRCG_ID = 201614

card = Card(KRCG_ID, "Valeriya Zinovieva")


@card.on(Hook.COMBAT_STRENGTH_MODIFIER)
def _strength(state: GameState, ctx: CombatStrengthModifierContext) -> int:
    vampire = state.players[ctx["player"]].vampires.get(ctx["vampire"])
    return 1 if vampire is not None and vampire.card.krcg_id == KRCG_ID else 0
