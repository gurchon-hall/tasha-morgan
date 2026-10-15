"""Pool transfer helpers shared by multiple phases. Centralises "pool cannot go
negative" and the oust check (§5), plus replay-log narration, for every call site."""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import TYPE_CHECKING

from .ousting import check_oust, resolve_pending_ousts

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


@contextmanager
def simultaneous_pool_losses(state: GameState) -> Iterator[None]:
    """Defer ousting until every pool loss of one event is applied (OQ-44, D-9): both
    at 0 pool from the same event is a tie. Nests; an exception discards queued ousts."""
    state.oust_deferral_depth += 1
    try:
        yield
    except BaseException:
        state.oust_deferral_depth -= 1
        if state.oust_deferral_depth == 0:
            state.pending_ousts.clear()
        raise
    state.oust_deferral_depth -= 1
    if state.oust_deferral_depth == 0:
        resolve_pending_ousts(state)


def lose_pool_simultaneously(state: GameState, losses: Mapping[str, int]) -> dict[str, int]:
    """Apply `losses` ({player: amount}) as one event; returns amounts lost.

    Application order is by player id, not seat, so the result never depends
    on `turn_order` (OQ-44).
    """
    lost: dict[str, int] = {}
    with simultaneous_pool_losses(state):
        for player in sorted(losses):
            lost[player] = lose_pool(state, player, losses[player])
    return lost


MIN_POOL_AFTER_VOLUNTARY_SPEND = 1
"""OQ-41/OQ-42, D-9 (project simplification, not a rulebook rule): a Methuselah may
not bring their own pool to 0 via a voluntary choice."""


def max_voluntary_spend(state: GameState, player: str) -> int:
    """Most pool `player` may voluntarily pay/burn (OQ-42): keeps them at 1+."""
    return max(0, state.players[player].pool - MIN_POOL_AFTER_VOLUNTARY_SPEND)


def can_afford_without_ousting(state: GameState, player: str, amount: int) -> bool:
    """True if `player` may voluntarily pay/burn `amount` pool (OQ-42). Every
    self-paid-cost option generator must gate on this; mandatory losses bypass it."""
    return amount <= max_voluntary_spend(state, player)
