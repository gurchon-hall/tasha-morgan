"""Damage-prevention hook wiring (`engine/hooks.py`, CLAUDE.md milestone-3
scaffolding pass; `engine/damage.py`'s "Prevent step"). No prevention card
(Rolling with the Punches, Soak) is implemented yet -- scenario tests for
the mechanism only, using a trivial fake provider.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.damage import (
    ROUND_STATE_CONTEXT_KEY,
    apply_damage,
    mandatory_full_prevention_active,
    mark_mandatory_full_prevention_active,
)
from vtesbot.engine.decision import Choice


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


def test_a_registered_provider_can_read_and_write_round_state():
    """OQ-55 plumbing: `DAMAGE_PREVENTION_HOOK`'s own context now carries
    `ROUND_STATE_CONTEXT_KEY`, mirroring every other round-scoped cap
    (`engine/combat.py`'s `ADDITIONAL_STRIKE_LIMIT_KEY`,
    `COMMITTED_STRIKE_KEY`). A once-per-round provider gates itself on a
    flag it wrote on an earlier call, within the same `round_state` dict --
    exactly the shape Soak needs for its own "only one Soak each round" cap.
    """
    def once_per_round_prevention(state, context):
        round_state = context.get(ROUND_STATE_CONTEXT_KEY)
        assert round_state is not None
        vampire_id = context["vampire"]
        if vampire_id in round_state.get("fake_prevent_used", set()):
            return []
        damage_box = context["damage"]
        if damage_box.get("normal", 0) <= 0:
            return []

        def _apply(s):
            round_state.setdefault("fake_prevent_used", set()).add(vampire_id)
            damage_box["normal"] = max(0, damage_box["normal"] - 1)

        return [hooks.HookOption(choice=Choice("use_fake_prevent", "Prevent 1"), apply=_apply)]

    hooks.register("damage_prevention", once_per_round_prevention)
    game = _one_vampire_game(capacity=3, blood=0)
    round_state: dict[str, object] = {}

    agent_first = ScriptedAgent("A")
    agent_first.expect("damage_prevention", "use_fake_prevent")
    game.state.agents["A"] = agent_first
    apply_damage(
        game.state,
        "A",
        game.vampire("V1"),
        normal=2,
        round_state=round_state,
    )
    agent_first.assert_exhausted()
    # 2 normal damage, 1 prevented by the hook -> 1 left, mended with no
    # blood available -> wounded.
    assert game.vampire("V1").wounded is True
    assert round_state["fake_prevent_used"] == {"V1"}

    # Same round, a second hit on the same vampire (e.g. an additional-strike
    # pair, OQ-55's own motivating case): the provider's own cap, read back
    # from the same `round_state` dict, suppresses the option entirely.
    agent_second = ScriptedAgent("A")
    game.state.agents["A"] = agent_second
    apply_damage(
        game.state,
        "A",
        game.vampire("V1"),
        normal=1,
        round_state=round_state,
    )
    agent_second.assert_exhausted()


def test_mandatory_full_prevention_is_automatic_for_the_rest_of_the_round():
    """OQ-55's remaining gap (Rolling with the Punches' superior clause): a
    provider's own `apply` marks `MANDATORY_FULL_PREVENTION_KEY` active via
    `mark_mandatory_full_prevention_active` on its first (freely chosen) offer;
    every later `apply_damage` call this round against the same vampire then
    has both normal and aggravated damage zeroed unconditionally, with no
    `DAMAGE_PREVENTION_HOOK` option even needing to fire again -- the mandatory
    automatic path, not a re-offered declinable choice.
    """

    def activate_mandatory_prevention(state, context):
        round_state = context.get(ROUND_STATE_CONTEXT_KEY)
        vampire_id = context["vampire"]
        if mandatory_full_prevention_active(round_state, vampire_id):
            return []  # already active -- nothing further to offer this round

        def _apply(s):
            mark_mandatory_full_prevention_active(round_state, vampire_id)
            context["damage"]["normal"] = 0
            context["damage"]["aggravated"] = 0

        return [
            hooks.HookOption(
                choice=Choice("activate_mandatory_prevent", "Prevent all this round"),
                apply=_apply,
            )
        ]

    hooks.register("damage_prevention", activate_mandatory_prevention)
    game = _one_vampire_game(capacity=3, blood=0)
    round_state: dict[str, object] = {}

    agent_first = ScriptedAgent("A")
    agent_first.expect("damage_prevention", "activate_mandatory_prevent")
    game.state.agents["A"] = agent_first
    apply_damage(
        game.state,
        "A",
        game.vampire("V1"),
        normal=1,
        round_state=round_state,
    )
    agent_first.assert_exhausted()
    assert game.vampire("V1").wounded is False
    assert mandatory_full_prevention_active(round_state, "V1") is True

    # Same round, a fresh strike with both normal and aggravated damage: fully
    # zeroed before `DAMAGE_PREVENTION_HOOK` even dispatches -- no Decision is
    # asked of the agent at all (an empty ScriptedAgent would raise if one were).
    agent_second = ScriptedAgent("A")
    game.state.agents["A"] = agent_second
    apply_damage(
        game.state,
        "A",
        game.vampire("V1"),
        normal=2,
        aggravated=1,
        round_state=round_state,
    )
    agent_second.assert_exhausted()
    assert game.vampire("V1").wounded is False
    assert game.vampire("V1").zone == "ready"
