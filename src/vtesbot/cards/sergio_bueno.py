"""Sergio Bueno (Vampire). krcg 201662. Snapshot: data/cards/201662.json
"Your" counters: placed by Sergio's controller. Only vampires block in this
engine, so the cost is always blood (Rulebook §8 Life). See ENG-044."""

from vtesbot.cards.card import Card
from vtesbot.engine.action import BlockAttemptCost
from vtesbot.engine.hook_contexts import BlockAttemptCostContext
from vtesbot.engine.hooks import Hook
from vtesbot.engine.state import GameState

KRCG_ID = 201662
BLOOD_COST = 1

card = Card(KRCG_ID, "Sergio Bueno")


@card.on(Hook.BLOCK_ATTEMPT_COST)
def _block_cost(state: GameState, ctx: BlockAttemptCostContext) -> BlockAttemptCost | None:
    actor, acting_vampire_id = ctx["actor"], ctx["acting_vampire"]
    if acting_vampire_id is None:
        return None
    sergio = state.players[actor].vampires.get(acting_vampire_id)
    if sergio is None or sergio.card.krcg_id != KRCG_ID:
        return None
    candidate = state.players[ctx["defender"]].vampires.get(ctx["candidate"])
    if candidate is None or candidate.corruption_counters.get(actor, 0) < 1:
        return None

    def _pay(_s: GameState) -> None:
        candidate.blood -= BLOOD_COST

    return BlockAttemptCost(can_pay=candidate.blood >= BLOOD_COST, pay=_pay)
