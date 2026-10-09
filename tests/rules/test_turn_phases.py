"""Turn sequence: Unlock, Master, Minion, Influence, Discard (Rulebook SS4)."""

from helpers import ScenarioBuilder
from vtesbot.engine.phases import play_turn


def test_turn_runs_five_phases_and_alternates_active_player():
    """With no vampires, no hand cards and no uncontrolled crypt cards, every
    phase this milestone resolves with zero decisions (nothing legal to do),
    so a full turn can run start to finish and hand control to the other
    player (Rulebook SS4 turn sequence)."""
    game = ScenarioBuilder(seed=1).player("P1").player("P2").build()
    state = game.state
    assert state.active_player == "P1"

    play_turn(state)

    assert state.active_player == "P2"
    assert state.turn_number == 2
    assert not state.game_over


def test_second_turn_keeps_alternating():
    game = ScenarioBuilder(seed=1).player("P1").player("P2").build()
    state = game.state

    play_turn(state)
    play_turn(state)

    assert state.active_player == "P1"
    assert state.turn_number == 3
