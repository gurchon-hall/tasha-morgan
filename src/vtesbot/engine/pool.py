"""Pool transfer helpers shared by multiple phases.

Centralises "pool cannot go negative" and the oust check (Rulebook SS5) so
every pool-loss site (bleed, influence refunds, contests, future cards)
triggers ousting consistently -- and, for the same reason, is the single
place a pool change is narrated into the replay log (`engine/log.py`'s
`record_event`, observability only), so every one of this module's ~20
call sites across `engine/`/`cards/` gets it for free.
"""

from typing import TYPE_CHECKING

from .ousting import check_oust

if TYPE_CHECKING:
    from .state import GameState


def gain_pool(state: GameState, player: str, amount: int) -> None:
    if amount <= 0:
        return
    p = state.players[player]
    p.pool += amount
    state.log.record_event(f"{player} gains {amount} pool (now {p.pool})")


def lose_pool(state: GameState, player: str, amount: int) -> int:
    """Reduce `player`'s pool by up to `amount` (floored at 0) and check ousting.

    Returns the amount actually lost.
    """
    if amount <= 0:
        return 0
    p = state.players[player]
    lost = min(amount, p.pool)
    p.pool -= lost
    if lost > 0:
        state.log.record_event(f"{player} loses {lost} pool (now {p.pool})")
    check_oust(state, player)
    return lost
