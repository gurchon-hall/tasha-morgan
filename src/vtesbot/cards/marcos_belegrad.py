"""Marcos Belegrad (Vampire). krcg 201702. Snapshot: data/cards/201702.json
1 pool per Methuselah who cast against, not per vote, pass or fail; "controlling
a minion casting" is the vote source's player. Later pool spends: ENG-057."""

from vtesbot.cards.card import Card
from vtesbot.engine.hook_contexts import ReferendumTalliedContext, VoteAgainstPoolCostContext
from vtesbot.engine.hooks import Hook
from vtesbot.engine.pool import lose_pool_simultaneously
from vtesbot.engine.state import GameState

KRCG_ID = 201702

card = Card(KRCG_ID, "Marcos Belegrad")


@card.on(Hook.REFERENDUM_TALLIED)
def _provide_marcos_belegrad(state: GameState, ctx: ReferendumTalliedContext) -> None:
    if ctx["caller_vampire"].card.krcg_id != KRCG_ID:
        return
    casters_against = {
        player for (player, _source_id, _votes, direction) in ctx["casts"] if direction == "against"
    }
    lose_pool_simultaneously(state, dict.fromkeys(casters_against, 1))


@card.on(Hook.VOTE_AGAINST_POOL_COST)
def _marcos_against_cost(state: GameState, ctx: VoteAgainstPoolCostContext) -> int:
    """Against is not offered if the tally burn would oust the caster (DES-009);
    a second against cast costs nothing more."""
    caller_vampire = ctx["caller_vampire"]
    if caller_vampire is None or caller_vampire.card.krcg_id != KRCG_ID:
        return 0
    player = ctx["player"]
    if any(p == player and d == "against" for (p, _s, _v, d) in ctx["casts"]):
        return 0
    return 1
