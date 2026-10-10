"""The generic card-hook dispatcher (`engine/hooks.py`, CLAUDE.md milestone-3
scaffolding pass) and its wiring into the block-attempt stealth/intercept
ping-pong (`engine/action.py`).

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism* (CLAUDE.md "Card hooks") using trivial fake providers, not a
real card -- real card effect modules and their own tests are
`card-implementer`'s next pass.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import attempt_block


@pytest.fixture(autouse=True)
def _clean_hooks():
    """Test isolation (CLAUDE.md "no global state"/`docs/DECISIONS.md` D-5):
    the hook catalogue is shared, process-wide, static state, so fake
    providers registered by a test must not leak into the next one."""
    yield
    hooks.clear()


def test_offer_returns_nothing_when_no_provider_is_registered():
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    assert hooks.offer("some_hook", game.state, player="P1") == []


def test_register_and_offer_a_fake_choice():
    from vtesbot.engine.decision import Choice

    def provider(state, context):
        return [hooks.HookOption(choice=Choice("use_fake", "Use the fake card"), apply=lambda s: 3)]

    hooks.register("fake_hook", provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()

    options = hooks.offer("fake_hook", game.state, player="P1")
    assert [o.choice.value for o in options] == ["use_fake"]
    assert options[0].apply(game.state) == 3


def test_unregister_removes_a_provider():
    from vtesbot.engine.decision import Choice

    def provider(state, context):
        return [hooks.HookOption(choice=Choice("x", "X"), apply=lambda s: 1)]

    hooks.register("fake_hook", provider)
    hooks.unregister("fake_hook", provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    assert hooks.offer("fake_hook", game.state, player="P1") == []


def test_sum_modifiers_adds_every_registered_providers_contribution():
    hooks.register("fake_strength", lambda state, context: 2)
    hooks.register("fake_strength", lambda state, context: 1)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    assert hooks.sum_modifiers("fake_strength", game.state, player="P1") == 3


def test_union_modifiers_returns_a_sorted_tuple_not_a_frozenset():
    """Rules-auditor finding (CLAUDE.md SS5 determinism): a `frozenset[str]`
    is a latent non-reproducible-ordering footgun for any future consumer
    that iterates it to build `Decision.choices` (Python's string hashing is
    randomized per process). `union_modifiers` must return a sorted tuple
    instead, with duplicates across providers collapsed exactly like a set
    union would."""
    hooks.register("fake_union", lambda state, context: ("cel", "obf"))
    hooks.register("fake_union", lambda state, context: ("aus", "obf"))  # "obf" duplicated
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()

    result = hooks.union_modifiers("fake_union", game.state, player="P1")

    assert result == ("aus", "cel", "obf")
    assert isinstance(result, tuple)


def test_offer_until_pass_loops_until_the_player_passes():
    from vtesbot.engine.decision import Choice

    calls = []

    def provider(state, context):
        return [hooks.HookOption(choice=Choice("tick", "Tick"), apply=lambda s: calls.append(1))]

    hooks.register("fake_loop", provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    agent = ScriptedAgent("P1")
    agent.expect("fake_loop", "tick")
    agent.expect("fake_loop", "tick")
    agent.expect("fake_loop", "pass")
    game.state.agents["P1"] = agent

    hooks.offer_until_pass(game.state, "fake_loop", "P1", context={})

    assert len(calls) == 2
    agent.assert_exhausted()


def test_resolve_impulse_window_closes_once_both_players_pass_in_succession():
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    p1 = ScriptedAgent("P1")
    p2 = ScriptedAgent("P2")
    game.state.agents["P1"] = p1
    game.state.agents["P2"] = p2
    # No providers registered: both players' first offer is empty, so the
    # window closes with zero decisions asked at all (CLAUDE.md "only when
    # needed": nothing legal to offer => no vacuous Decision).

    hooks.resolve_impulse_window(game.state, "fake_window", "P1", "P2", context={})

    p1.assert_exhausted()
    p2.assert_exhausted()


def test_resolve_impulse_window_snaps_back_to_the_acting_player_after_any_use():
    """CLAUDE.md rule 4: "after any effect is used the impulse returns to the
    acting Methuselah" -- even when it was the *other* player who just used
    one. Each provider is one-shot (closure-tracked), mirroring a real card
    being spent: P1 (acting) is offered first and uses their option (the
    window does not hand control to P2 immediately -- it re-offers P1 first,
    "may chain effects"); once P1 has nothing left the window silently moves
    to P2 (CLAUDE.md "only when needed": nothing to offer, no decision
    asked); P2 uses their option, and the impulse snaps back to P1 (not back
    to P2) per the rule above -- P1 again has nothing left, then neither
    does P2, and the window closes.
    """
    from vtesbot.engine.decision import Choice

    p1_used = [False]
    p2_used = [False]

    def p1_provider(state, context):
        if context.get("player") != "P1" or p1_used[0]:
            return []

        def _apply(s):
            p1_used[0] = True

        return [hooks.HookOption(choice=Choice("p1_add", "P1 adds"), apply=_apply)]

    def p2_provider(state, context):
        if context.get("player") != "P2" or p2_used[0]:
            return []

        def _apply(s):
            p2_used[0] = True

        return [hooks.HookOption(choice=Choice("p2_add", "P2 adds"), apply=_apply)]

    hooks.register("fake_window", p1_provider)
    hooks.register("fake_window", p2_provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    p1 = ScriptedAgent("P1").expect("fake_window", "p1_add")
    p2 = ScriptedAgent("P2").expect("fake_window", "p2_add")
    game.state.agents["P1"] = p1
    game.state.agents["P2"] = p2

    hooks.resolve_impulse_window(game.state, "fake_window", "P1", "P2", context={})

    assert p1_used[0] is True
    assert p2_used[0] is True
    p1.assert_exhausted()
    p2.assert_exhausted()


def test_block_attempt_offers_no_stealth_or_intercept_decision_without_providers():
    """Zero-regression check: with no stealth/intercept provider registered,
    `attempt_block` behaves exactly as before this pass's hook wiring (see
    `tests/rules/test_block_attempts.py`)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    defender.assert_exhausted()


def test_intercept_modifier_hook_can_turn_a_failing_block_into_a_success():
    """A fake intercept-modifier provider (standing in for a future reaction
    card like Second Tradition: Domain's basic clause) lets the blocking
    Methuselah add +2 intercept against a base_stealth=1 (hunt-level)
    attempt, which the milestone-2 engine always failed (0 >= 1 is false)."""
    from vtesbot.engine.decision import Choice

    def intercept_provider(state, context):
        if context.get("player") != "P2":
            return []
        return [
            hooks.HookOption(choice=Choice("use_intercept_card", "+2 intercept"), apply=lambda s: 2)
        ]

    hooks.register("intercept_modifier", intercept_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("intercept_modifier", "use_intercept_card")
    # Impulse returns to the acting Methuselah (CLAUDE.md rule 4): with
    # intercept(2) >= stealth(1) now, P1 may add stealth but has no provider.
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=1)

    assert blocker is not None
    assert blocker.instance_id == "B1"
    defender.assert_exhausted()


def test_stealth_modifier_hook_lets_the_actor_rescue_a_currently_succeeding_block():
    """With a stealth-modifier provider for the acting player, a bleed
    (base_stealth=0, which always succeeds against a bare blocker) can be
    pushed back out of reach of the blocker's (unmodified) intercept."""
    from vtesbot.engine.decision import Choice

    def stealth_provider(state, context):
        if context.get("player") != "P1":
            return []
        return [
            hooks.HookOption(choice=Choice("use_stealth_card", "+1 stealth"), apply=lambda s: 1)
        ]

    hooks.register("stealth_modifier", stealth_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("stealth_modifier", "use_stealth_card")
    # After the delta applies, stealth(1) > intercept(0): it is the
    # blocker's turn next, who has no intercept provider, so the window
    # closes without asking the actor again (CLAUDE.md "only when needed").
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")  # no intercept provider to try again with
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    actor.assert_exhausted()
    defender.assert_exhausted()
