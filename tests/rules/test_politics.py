"""Political action announce/block scaffolding (`engine/politics.py`,
CLAUDE.md milestone-3 scaffolding pass). The referendum-resolution part is
intentionally unresolved (`docs/OPEN_QUESTIONS.md` OQ-6); only the generic
"announce -> block attempt -> (blocked: combat) | (unblocked: OQ-6)" path is
covered here.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.errors import UnresolvedRulingError
from vtesbot.engine.politics import political_action


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def test_a_blocked_political_action_goes_to_combat_and_never_raises_oq6():
    """Political action's baseline stealth is +1 (Rulebook SS4 default
    action list), which -- like hunt's own +1 baseline (see
    `tests/rules/test_minion_hunt.py`) -- always evades a bare block attempt
    with no intercept-granting card implemented; a fake intercept-modifier
    provider stands in for one here purely to exercise the "blocked ->
    combat" path end to end."""

    def fake_intercept(state, context):
        if context.get("player") != "P2":
            return []
        return [
            hooks.HookOption(choice=Choice("use_fake_intercept", "+2 intercept"), apply=lambda s: 2)
        ]

    hooks.register("intercept_modifier", fake_intercept)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("intercept_modifier", "use_fake_intercept")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    political_action(game.state, "P1", game.vampire("V1"))

    assert game.vampire("V1").locked is True  # announcing locks the acting vampire
    assert game.vampire("B1").locked is True  # a successful block locks the blocker
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_an_unblocked_political_action_raises_oq6_instead_of_guessing():
    """With no candidate blocker ready, the defender is never even offered a
    choice ("only when needed"), and the political action proceeds straight
    to the unresolved referendum gap."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")

    with pytest.raises(UnresolvedRulingError) as excinfo:
        political_action(game.state, "P1", game.vampire("V1"))

    assert excinfo.value.oq_id == "OQ-6"


def test_a_declined_block_attempt_also_raises_oq6():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    defender = ScriptedAgent("P2").expect("block_attempt", "decline")
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = defender

    with pytest.raises(UnresolvedRulingError) as excinfo:
        political_action(game.state, "P1", game.vampire("V1"))

    assert excinfo.value.oq_id == "OQ-6"
    defender.assert_exhausted()
