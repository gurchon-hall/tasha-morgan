"""The `"stealth_modifier"`/`"intercept_modifier"` hook context's `action`
discriminator (OQ-9, `docs/OPEN_QUESTIONS.md`): `engine/action.py::
perform_minion_action`/`attempt_block`/`_duel_stealth_intercept` thread an
explicit `action` name (e.g. `"bleed"`, `"hunt"`, `"political_action"`)
through to both hooks' context, and into the `"block_attempt"` decision's
own context, so a provider can tell which minion action is in progress
instead of guessing from `base_stealth`'s numeric value (a sourced need:
Bonding's superior clause, "[DOM] Cannot be used to increase the stealth of
a non-bleed action").

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using trivial fake providers -- Bonding itself remains
`card-implementer`'s job once this capability exists.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import attempt_block
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.minion import minion_phase


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def test_attempt_block_without_an_explicit_action_defaults_to_none():
    """Zero-regression check: callers that do not pass `action` (e.g. every
    existing `tests/rules/test_block_attempts.py` call) still work, and the
    context carries `action=None` rather than raising."""
    seen_context = {}

    def provider(state, context):
        seen_context.update(context)
        return []

    hooks.register("stealth_modifier", provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    game.state.agents["P2"] = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    assert seen_context["action"] is None


def test_attempt_block_forwards_an_explicit_action_into_the_block_attempt_decision():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    seen = {}

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "block_attempt":
                seen["action"] = decision.context.get("action")
            return super().decide(observation, decision)

    defender = RecordingAgent("P2").expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    attempt_block(game.state, "P1", "P2", base_stealth=0, action="bleed")

    assert seen["action"] == "bleed"


def test_stealth_modifier_hook_context_carries_the_action_name():
    seen_context = {}

    def stealth_provider(state, context):
        seen_context.update(context)
        return []

    hooks.register("stealth_modifier", stealth_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    game.state.agents["P2"] = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")

    attempt_block(game.state, "P1", "P2", base_stealth=0, action="bleed")

    assert seen_context["action"] == "bleed"


def test_intercept_modifier_hook_context_carries_the_action_name():
    seen_context = {}

    def intercept_provider(state, context):
        seen_context.update(context)
        return []

    hooks.register("intercept_modifier", intercept_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    # base_stealth=1 (hunt-level): stealth(1) > intercept(0), so the
    # intercept branch of the ping-pong is offered first; with no option
    # from the recording provider the attempt fails and loops back.
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    attempt_block(game.state, "P1", "P2", base_stealth=1, action="hunt")

    assert seen_context["action"] == "hunt"


def test_a_bleed_only_provider_fires_during_a_bleed_action_not_a_hunt():
    """A fake stand-in for Bonding's superior clause ("[DOM] Cannot be used
    to increase the stealth of a non-bleed action"): gates itself on
    `context["action"] == "bleed"`, exactly the restriction OQ-9 was blocked
    on being unable to express."""

    def bleed_only_stealth(state, context):
        if context.get("action") != "bleed":
            return []
        return [hooks.HookOption(choice=Choice("bonding", "+1 stealth"), apply=lambda s: 1)]

    hooks.register("stealth_modifier", bleed_only_stealth)

    # Bleed: base_stealth=0, intercept=0 -> block currently succeeds -> the
    # actor's stealth_modifier is offered and fires.
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1").expect("stealth_modifier", "bonding")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")  # now stealth(1) > intercept(0), no more to try
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0, action="bleed")

    assert blocker is None  # stealth bumped to 1, out of the blocker's reach
    actor.assert_exhausted()
    defender.assert_exhausted()

    # Hunt: base_stealth=1, same fake provider offers nothing (action !=
    # "bleed"), so the block attempt proceeds with no stealth decision at
    # all -- the actor's script would fail if asked anything.
    builder2 = ScenarioBuilder(seed=1)
    builder2.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder2.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game2 = builder2.build()
    actor2 = ScriptedAgent("P1")  # no expectations: must not be asked anything
    defender2 = ScriptedAgent("P2").expect("block_attempt", "decline")
    game2.state.agents["P1"] = actor2
    game2.state.agents["P2"] = defender2

    attempt_block(game2.state, "P1", "P2", base_stealth=1, action="hunt")

    actor2.assert_exhausted()
    defender2.assert_exhausted()


def test_minion_phase_bleed_threads_action_bleed_end_to_end():
    """`engine/phases/minion.py::_perform_bleed` is the real production call
    site; this proves it actually passes `action="bleed"` all the way
    through `perform_minion_action` -> `attempt_block` -> the hook context,
    not just that the lower-level helpers *can* forward it."""
    seen = []

    def recorder(state, context):
        seen.append(context.get("action"))
        return []

    hooks.register("stealth_modifier", recorder)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    # Bleed's 0 baseline stealth means a block, once attempted, always
    # succeeds in this scaffold (no intercept providers) -- combat follows.
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert "bleed" in seen
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_minion_phase_hunt_threads_action_hunt_end_to_end():
    """Same production call site as above, via `_perform_hunt`."""
    seen = []

    def recorder(state, context):
        seen.append(context.get("action"))
        return []

    hooks.register("intercept_modifier", recorder)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "hunt")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    # Hunt's +1 baseline stealth always exceeds the hardcoded 0 intercept
    # (no intercept bonus from the empty-returning recorder), so the
    # attempt fails and the defender is re-offered another attempt or decline.
    defender.expect("block_attempt", "decline")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert "hunt" in seen
    actor.assert_exhausted()
    defender.assert_exhausted()
