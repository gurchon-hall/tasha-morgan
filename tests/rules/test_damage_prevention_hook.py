"""Damage-prevention hook wiring (`engine/hooks.py`, CLAUDE.md milestone-3
scaffolding pass; `engine/damage.py`'s "Prevent step"). No prevention card
(Rolling with the Punches, Soak) is implemented yet -- scenario tests for
the mechanism only, using a trivial fake provider.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def _one_vampire_game(capacity: int = 3, blood: int = 0):
    builder = ScenarioBuilder(seed=1)
    builder.player("A").ready_vampire("V1", capacity=capacity, blood=blood)
    builder.player("B")
    return builder.build()


def test_no_prevention_decision_without_a_provider():
    """Zero-regression check: byte-for-byte the milestone-2 result."""
    game = _one_vampire_game(capacity=3, blood=0)
    game.state.agents["A"] = ScriptedAgent("A")

    game.apply_damage(target="V1", normal=1)

    assert game.vampire("V1").wounded is True


def test_a_registered_provider_can_prevent_all_normal_damage():
    def fake_prevention(state, context):
        if context.get("player") != "A":
            return []
        damage_box = context["damage"]

        def _apply(s):
            damage_box["normal"] = 0

        return [hooks.HookOption(choice=Choice("use_fake_prevent", "Prevent all"), apply=_apply)]

    hooks.register("damage_prevention", fake_prevention)
    game = _one_vampire_game(capacity=3, blood=0)
    agent = ScriptedAgent("A")
    agent.expect("damage_prevention", "use_fake_prevent")
    # The fake provider is not one-shot (always offers itself); "only when
    # needed" still applies -- the player must explicitly pass once there is
    # nothing left to prevent.
    agent.expect("damage_prevention", "pass")
    game.state.agents["A"] = agent

    game.apply_damage(target="V1", normal=1)

    assert game.vampire("V1").wounded is False
    agent.assert_exhausted()


def test_declining_prevention_leaves_damage_unchanged():
    def fake_prevention(state, context):
        if context.get("player") != "A":
            return []
        return [
            hooks.HookOption(choice=Choice("use_fake_prevent", "Prevent all"), apply=lambda s: None)
        ]

    hooks.register("damage_prevention", fake_prevention)
    game = _one_vampire_game(capacity=3, blood=0)
    agent = ScriptedAgent("A").expect("damage_prevention", "pass")
    game.state.agents["A"] = agent

    game.apply_damage(target="V1", normal=1)

    assert game.vampire("V1").wounded is True
    agent.assert_exhausted()
