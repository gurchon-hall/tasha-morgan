"""Ousting and victory (Rulebook §5). Pool 0 -> ousted; predator gets 1 VP
+ 6 pool, +1 VP if last Methuselah -- both land on one player here (§3).
Simultaneous ousts (DES-010) tie: 1 VP each, no pool."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import GameState

OUST_PREDATOR_POOL = 6


def check_oust(state: GameState, player: str) -> None:
    """Called after any pool loss; oust `player` if their pool has reached 0."""
    if state.game_over or state.is_eliminated(player):
        return
    if state.players[player].pool > 0:
        return
    if state.oust_deferral_depth > 0:
        if player not in state.pending_ousts:
            state.pending_ousts.append(player)
        return

    state.eliminated.add(player)
    predator = state.other_player(player)
    # 1 VP for ousting the prey, + 1 VP for being the last Methuselah remaining
    # (both apply to the same event in a 2-player duel, see module docstring).
    state.victory_points[predator] = state.victory_points.get(predator, 0) + 2
    state.players[predator].pool += OUST_PREDATOR_POOL
    state.game_over = True
    state.winner = predator
    state.log.record_event(
        f"{player} is OUSTED -- {predator} wins "
        f"(VP={state.victory_points[predator]}, pool={state.players[predator].pool})"
    )


def resolve_pending_ousts(state: GameState) -> None:
    """Resolve ousts queued while deferred: both at 0 pool -> tie (see
    module docstring), one -> `check_oust`."""
    pending = [p for p in state.pending_ousts if state.players[p].pool <= 0]
    state.pending_ousts.clear()
    if state.game_over:
        return
    if len(pending) < len(state.turn_order):
        for player in pending:
            check_oust(state, player)
        return
    for player in sorted(pending):
        state.eliminated.add(player)
        state.victory_points[player] = state.victory_points.get(player, 0) + 1
    state.game_over = True
    state.winner = None
    for player in sorted(pending):
        state.log.record_event(
            f"{player} is OUSTED -- simultaneous ousts, TIE, no winner "
            f"(VP={state.victory_points[player]})"
        )
