"""Pool transfer helpers shared by multiple phases.

Centralises "pool cannot go negative" and the oust check (Rulebook SS5) so
every pool-loss site (bleed, influence refunds, contests, future cards)
triggers ousting consistently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .ousting import check_oust

if TYPE_CHECKING:
    from .state import GameState


def gain_pool(state: GameState, player: str, amount: int) -> None:
    if amount <= 0:
        return
    state.players[player].pool += amount


def lose_pool(state: GameState, player: str, amount: int) -> int:
    """Reduce `player`'s pool by up to `amount` (floored at 0) and check ousting.

    Returns the amount actually lost.
    """
    if amount <= 0:
        return 0
    p = state.players[player]
    lost = min(amount, p.pool)
    p.pool -= lost
    check_oust(state, player)
    return lost
