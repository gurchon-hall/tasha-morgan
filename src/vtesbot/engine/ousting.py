"""Ousting and victory.

Source: Rulebook SS5 Ending the Game (per the `vtes-rules-reference` skill
condensed mapping): "Pool 0 -> ousted. Prey ousted -> predator gets 1 VP + 6
pool. Last Methuselah gets +1 VP. With two players left, each is the other's
prey." (Withdrawal rules, Rulebook SS5 Advanced, are out of scope.)

2P structural consequence (CLAUDE.md SS3, confirmed settled -- not OQ-1,
which is scoped to card-text prey/predator wording): in a 2-player duel
a single oust normally ends the game, and the surviving Methuselah is
*simultaneously* the ousted player's predator and the last Methuselah
remaining, so both bonuses apply to that one player: 1 VP (ousting prey) + 1
VP (last Methuselah) + 6 pool, and the game ends immediately.

Simultaneous ousts (OQ-44, user ruling 2026-10-13, `docs/DECISIONS.md` D-9):
when both pools hit 0 from the same event (`pool.simultaneous_pool_losses`)
the game is a tie: `winner = None`. Rulebook SS5: "In the case of a tie there
is no winner of the game"; "EXCEPTION: If a Methuselah is ousted at the same
time that their prey is ousted, the Methuselah gets the victory point but
does not gain 6 pool counters" (also LSJ 20000309, "players whose prey gets
ousted get a victory point, even if they are being ousted themselves"). Each
Methuselah is the other's prey, so each gets 1 VP, no pool, and nobody is the
last Methuselah remaining (no extra VP).
"""

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
    """Resolve the ousts queued while deferred: both at 0 pool -> tie
    (Rulebook SS5 tie + EXCEPTION, see module docstring), one -> `check_oust`."""
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
