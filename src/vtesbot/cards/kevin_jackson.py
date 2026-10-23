"""Kevin Jackson (Vampire). krcg 201629. Snapshot: data/cards/201629.json
Two one-way bonuses, each matched on his krcg id; the opponent belongs to the
other player (RUL-001)."""

from vtesbot.cards.card import Card
from vtesbot.engine.hook_contexts import CombatStrengthModifierContext
from vtesbot.engine.hooks import Hook
from vtesbot.engine.state import GameState

KRCG_ID = 201629
BRUJAH = "Brujah"

card = Card(KRCG_ID, "Kevin Jackson")


@card.on(Hook.COMBAT_STRENGTH_MODIFIER)
def _strength(state: GameState, ctx: CombatStrengthModifierContext) -> int:
    player = ctx["player"]
    vampire = state.players[player].vampires.get(ctx["vampire"])
    opponent = state.players[state.other_player(player)].vampires.get(ctx["opponent"])
    if vampire is None or opponent is None:
        return 0
    bonus = 0
    if vampire.card.krcg_id == KRCG_ID and opponent.card.clan == BRUJAH:
        bonus += 1
    if vampire.card.clan == BRUJAH and opponent.card.krcg_id == KRCG_ID:
        bonus += 1
    return bonus
