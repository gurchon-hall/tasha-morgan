"""Master phase's real decision structure (CLAUDE.md milestone-3 scaffolding
pass; `engine/phases/master.py`), driven entirely by the `"master_phase_play"`
hook (`engine/hooks.py`). No master card is implemented yet -- these are
scenario tests for the *mechanism*, using a trivial fake card, per the
`rules-scenario-test` skill.

Source: Rulebook SS4 Master Phase (per the `vtes-rules-reference` skill
condensed mapping): "1 master phase action by default; trifles grant one
extra (max one per phase); ... unused actions are lost."
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.master import master_phase


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def test_no_decision_is_raised_with_no_master_card_provider_registered():
    """Zero-regression check: byte-for-byte the milestone-2 no-op."""
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    agent = ScriptedAgent("P1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()  # no decision at all was raised


def test_playing_a_non_trifle_card_consumes_the_single_action():
    plays = []

    def fake_master_card(state, context):
        if context.get("player") != "P1":
            return []
        return [
            hooks.HookOption(
                choice=Choice("play_fake_master", "Play Fake Master Card"),
                apply=lambda s: plays.append("fake_master") or False,
            )
        ]

    hooks.register("master_phase_play", fake_master_card)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    agent = ScriptedAgent("P1").expect("master_phase_action", "play_fake_master")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert plays == ["fake_master"]
    agent.assert_exhausted()  # the single action is spent: no second offer


def test_passing_ends_the_phase_without_playing():
    def fake_master_card(state, context):
        if context.get("player") != "P1":
            return []
        return [
            hooks.HookOption(
                choice=Choice("play_fake_master", "Play Fake Master Card"), apply=lambda s: False
            )
        ]

    hooks.register("master_phase_play", fake_master_card)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    agent = ScriptedAgent("P1").expect("master_phase_action", "pass")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_playing_a_trifle_grants_one_extra_action_max_once_per_phase():
    """Rulebook SS4: "trifles grant one extra [action] (max one per phase)"."""
    plays = []

    def fake_trifle(state, context):
        if context.get("player") != "P1":
            return []
        return [
            hooks.HookOption(
                choice=Choice("play_fake_trifle", "Play Fake Trifle"),
                apply=lambda s: plays.append("trifle") or True,
            )
        ]

    hooks.register("master_phase_play", fake_trifle)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "play_fake_trifle")  # base action (+1 extra granted)
    agent.expect("master_phase_action", "play_fake_trifle")  # the one extra trifle action
    # Both actions (base + the one trifle bonus) are now spent
    # (actions_remaining reaches 0 after the 2nd play; the trifle bonus is
    # capped at one per phase), so the phase ends without a third offer.
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert plays == ["trifle", "trifle"]
    agent.assert_exhausted()
