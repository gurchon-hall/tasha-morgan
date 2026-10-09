"""Ousting and victory (Rulebook SS5 Ending the Game).

"Pool 0 -> ousted. Prey ousted -> predator gets 1 VP + 6 pool. Last
Methuselah gets +1 VP. With two players left, each is the other's prey."
2P structural consequence (CLAUDE.md SS3, settled core rule): the sole
survivor of a 2-player duel collects both bonuses at once and the game ends.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine.ousting import check_oust


def test_pool_at_zero_ousts_and_ends_the_game():
    game = ScenarioBuilder(seed=1).player("P1", pool=10).player("P2", pool=0).build()

    check_oust(game.state, "P2")

    assert "P2" in game.state.eliminated
    assert game.state.game_over is True
    assert game.state.winner == "P1"
    assert game.state.victory_points["P1"] == 2  # 1 (ousted prey) + 1 (last Methuselah)
    assert game.pool_of("P1") == 16  # 10 + 6


def test_positive_pool_does_not_oust():
    game = ScenarioBuilder(seed=1).player("P1", pool=10).player("P2", pool=1).build()

    check_oust(game.state, "P2")

    assert "P2" not in game.state.eliminated
    assert game.state.game_over is False


def test_checking_an_already_eliminated_player_is_a_no_op():
    game = ScenarioBuilder(seed=1).player("P1", pool=10).player("P2", pool=0).build()
    check_oust(game.state, "P2")
    pool_after_first = game.pool_of("P1")

    check_oust(game.state, "P2")

    assert game.pool_of("P1") == pool_after_first  # no double bonus


def test_minion_phase_decision_still_runs_after_oust_check_is_a_no_op_once_over():
    """Sanity: once game_over is set, no further decisions are solicited from
    either agent for the rest of the (already-ended) turn."""
    game = ScenarioBuilder(seed=1).player("P1", pool=10).player("P2", pool=0).build()
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")

    check_oust(game.state, "P2")  # would raise if it asked anything

    assert game.state.game_over is True
