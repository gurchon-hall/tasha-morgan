"""Discard phase (Rulebook SS4): discard + replace, or pass.

Event play ("play one event") is out of scope this milestone (no event
cards are implemented), so only discard+replace or passing is offered.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine.phases.discard import discard_phase


def test_discard_and_replace_draws_from_library():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1")
    p1.hand_cards(["Alpha", "Beta"])
    p1.library_cards(["Gamma"])
    builder.player("P2")
    game = builder.build()
    agent = ScriptedAgent("P1").expect("discard_phase_action", "discard:0")
    game.state.agents["P1"] = agent

    discard_phase(game.state, "P1")

    hand_names = [c.name for c in game.state.players["P1"].hand]
    assert hand_names == ["Beta", "Gamma"]
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Alpha"]
    agent.assert_exhausted()


def test_passing_the_discard_phase_action_changes_nothing():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1")
    p1.hand_cards(["Alpha"])
    builder.player("P2")
    game = builder.build()
    agent = ScriptedAgent("P1").expect("discard_phase_action", "pass")
    game.state.agents["P1"] = agent

    discard_phase(game.state, "P1")

    assert [c.name for c in game.state.players["P1"].hand] == ["Alpha"]
    agent.assert_exhausted()


def test_empty_hand_skips_the_decision_entirely():
    """ "Only when needed": nothing legal to discard means no decision is raised."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1")
    builder.player("P2")
    game = builder.build()
    game.state.agents["P1"] = ScriptedAgent("P1")  # would fail loudly if asked anything

    discard_phase(game.state, "P1")  # must not raise
