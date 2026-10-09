"""Ousting and victory.

Source: Rulebook SS5 Ending the Game (per the `vtes-rules-reference` skill
condensed mapping): "Pool 0 -> ousted. Prey ousted -> predator gets 1 VP + 6
pool. Last Methuselah gets +1 VP. With two players left, each is the other's
prey." (Withdrawal rules, Rulebook SS5 Advanced, are out of scope.)

2P structural consequence (CLAUDE.md SS3, confirmed settled -- not OQ-1,
which is scoped to card-text prey/predator wording): in a 2-player duel
there is only ever one oust event, and the single surviving Methuselah is
*simultaneously* the ousted player's predator and the last Methuselah
remaining, so both bonuses apply to that one player: 1 VP (ousting prey) + 1
VP (last Methuselah) + 6 pool, and the game ends immediately.
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

    state.eliminated.add(player)
    predator = state.other_player(player)
    # 1 VP for ousting the prey, + 1 VP for being the last Methuselah remaining
    # (both apply to the same event in a 2-player duel, see module docstring).
    state.victory_points[predator] = state.victory_points.get(predator, 0) + 2
    state.players[predator].pool += OUST_PREDATOR_POOL
    state.game_over = True
    state.winner = predator
