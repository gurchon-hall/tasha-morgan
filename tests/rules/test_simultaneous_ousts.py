"""Simultaneous ousts (OQ-44, user ruling 2026-10-13: both Methuselahs reaching
0 pool from the same event is a tie, no winner).

Rulebook SS5 Ending the Game: "In the case of a tie there is no winner of the
game"; "EXCEPTION: If a Methuselah is ousted at the same time that their prey
is ousted, the Methuselah gets the victory point but does not gain 6 pool
counters." In a duel each is the other's prey, so each gets 1 VP, no pool.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine.errors import GameOverError
from vtesbot.engine.pool import lose_pool, lose_pool_simultaneously, simultaneous_pool_losses


def test_both_to_zero_in_one_event_is_a_tie():
    game = ScenarioBuilder(seed=1).player("P1", pool=2).player("P2", pool=3).build()

    lose_pool_simultaneously(game.state, {"P1": 5, "P2": 5})

    assert game.state.game_over is True
    assert game.state.winner is None
    assert game.state.eliminated == {"P1", "P2"}
    assert game.state.victory_points == {"P1": 1, "P2": 1}
    assert game.pool_of("P1") == 0
    assert game.pool_of("P2") == 0


def test_tie_result_is_independent_of_turn_order_and_dict_order():
    results = []
    for order in (["P1", "P2"], ["P2", "P1"]):
        game = ScenarioBuilder(seed=1).player("P1", pool=1).player("P2", pool=1).build()
        game.state.turn_order = order
        lose_pool_simultaneously(game.state, {order[1]: 1, order[0]: 1})
        results.append((game.state.winner, game.state.eliminated, game.state.victory_points))
    assert results[0] == results[1]


def test_only_one_to_zero_is_an_ordinary_oust():
    game = ScenarioBuilder(seed=1).player("P1", pool=10).player("P2", pool=2).build()

    lose_pool_simultaneously(game.state, {"P1": 1, "P2": 2})

    assert game.state.winner == "P1"
    assert game.state.eliminated == {"P2"}
    assert game.state.victory_points["P1"] == 2
    assert game.pool_of("P1") == 15  # 10 - 1 + 6


def test_nobody_at_zero_nobody_ousted():
    game = ScenarioBuilder(seed=1).player("P1", pool=10).player("P2", pool=5).build()

    lose_pool_simultaneously(game.state, {"P1": 1, "P2": 1})

    assert game.state.game_over is False
    assert game.state.eliminated == set()


def test_deferral_nests_and_resolves_only_at_the_outermost_exit():
    game = ScenarioBuilder(seed=1).player("P1", pool=1).player("P2", pool=1).build()

    with simultaneous_pool_losses(game.state):
        with simultaneous_pool_losses(game.state):
            lose_pool(game.state, "P1", 1)
        assert game.state.game_over is False
        lose_pool(game.state, "P2", 1)
        assert game.state.game_over is False

    assert game.state.game_over is True
    assert game.state.winner is None


def test_state_asks_nothing_after_a_tie():
    game = ScenarioBuilder(seed=1).player("P1", pool=1).player("P2", pool=1).build()
    lose_pool_simultaneously(game.state, {"P1": 1, "P2": 1})

    from vtesbot.engine.decision import Choice, Decision

    game.state.agents["P1"] = ScriptedAgent("P1")
    with pytest.raises(GameOverError):
        game.state.ask(Decision(player="P1", kind="x", choices=(Choice("a", "a"),)))


def test_ask_unless_forced_logs_a_forced_entry_without_calling_the_agent():
    from vtesbot.engine.decision import Choice, Decision

    game = ScenarioBuilder(seed=1).player("P1", pool=5).player("P2", pool=5).build()
    game.state.agents["P1"] = ScriptedAgent("P1")  # empty script: any call would raise

    choice = game.state.ask_unless_forced(
        Decision(player="P1", kind="x", choices=(Choice("only", "only"),))
    )

    assert choice.value == "only"
    assert [e.kind for e in game.state.log.entries] == ["forced"]
    assert game.state.log.entries[0].data["choice"] == "only"


def test_exception_inside_the_deferral_aborts_without_resolving_pending_ousts():
    """Documented convention: an exception at the outermost level clears the
    queued ousts and re-raises; no oust is resolved. Exceptions are engine
    errors that abort the game, so no partial oust decision is made."""
    game = ScenarioBuilder(seed=1).player("P1", pool=1).player("P2", pool=1).build()

    with pytest.raises(RuntimeError):
        with simultaneous_pool_losses(game.state):
            lose_pool(game.state, "P1", 1)
            lose_pool(game.state, "P2", 1)
            raise RuntimeError("boom")

    assert game.state.oust_deferral_depth == 0
    assert not game.state.pending_ousts
    assert game.state.game_over is False
    assert game.state.eliminated == set()
