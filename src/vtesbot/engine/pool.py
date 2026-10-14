"""Pool transfer helpers shared by multiple phases.

Centralises "pool cannot go negative" and the oust check (Rulebook SS5) so
every pool-loss site (bleed, influence refunds, contests, future cards)
triggers ousting consistently -- and, for the same reason, is the single
place a pool change is narrated into the replay log (`engine/log.py`'s
`record_event`, observability only), so every one of this module's ~20
call sites across `engine/`/`cards/` gets it for free.
"""

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
    """Defer ousting until every pool loss of one event has been applied.

    OQ-44 (user ruling 2026-10-13, `docs/DECISIONS.md` D-9): Rulebook SS5
    Ending the Game ("In the case of a tie there is no winner") with both
    Methuselahs at 0 pool from the same event is a tie. Within the block
    `check_oust` only queues; on the outermost normal exit the queue is
    resolved once (`ousting.resolve_pending_ousts`). Nests. "Same event" is
    narrow: one card effect / one simultaneous strike pair.

    On an exception at the outermost level the queued ousts are discarded
    and the exception re-raised, resolving nothing: exceptions are engine
    errors that abort the game, never a legal outcome to decide an oust on.
    """
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
"""OQ-41/OQ-42 (user ruling 2026-10-13; project simplification for the 2P
duel, `docs/DECISIONS.md` D-9 -- not a rulebook rule): a Methuselah may not
bring their own pool to 0 through their own voluntary choices."""


def max_voluntary_spend(state: GameState, player: str) -> int:
    """Most pool `player` may voluntarily pay/burn (OQ-42): keeps them at 1+."""
    return max(0, state.players[player].pool - MIN_POOL_AFTER_VOLUNTARY_SPEND)


def can_afford_without_ousting(state: GameState, player: str, amount: int) -> bool:
    """True if `player` may voluntarily pay/burn `amount` pool (OQ-42).

    Every option generator offering a self-paid pool cost must gate on this
    (or `max_voluntary_spend`). Mandatory losses (bleed, forced card
    effects) bypass it and use `lose_pool` directly.
    """
    return amount <= max_voluntary_spend(state, player)
