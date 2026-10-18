"""`FORCE_BLOCK_ATTEMPT_FAILURE_HOOK` (`engine/action.py`, OQ-65): an
acting-side sibling of `INTERCEPT_DECREASE_HOOK`/`STEALTH_INCREASE_HOOK`,
offered reactively once a block candidate is already fixed, in *both*
branches of `_duel_stealth_intercept`: merged into the same `Decision` as
those two siblings while the attempt is currently succeeding, and offered
alone, after the defender has declined/exhausted `INTERCEPT_MODIFIER_HOOK`,
while the attempt is already failing on the raw numbers (rules-auditor
finding on this file's first landing -- its own non-numeric "cannot attempt
to block this action again" half has nothing to do with whether the current
numbers already fail, so "only when needed" (OQ-31/39), which keeps the
*numeric* modifiers out of that branch, must not keep this one out too).
Choosing it from the "succeeds" branch makes `_duel_stealth_intercept`
return `forced_failure=True`, which `attempt_block` reads *before* comparing
`intercept >= stealth` at all: the attempt fails outright, independent of
the numbers in play -- distinct from an extreme `INTERCEPT_DECREASE_HOOK`
delta, which would still let the defender respond with more intercept
before the duel ends. Choosing it from the already-failing branch simply
runs its own `apply` (the numbers already mean failure).

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a trivial fake provider -- `cards/forced_confessional.py`
(krcg 102250), which names this gap, is `card-implementer`'s own wiring of
it, proven separately in `tests/cards/test_forced_confessional.py`.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import (
    FORCE_BLOCK_ATTEMPT_FAILURE_HOOK,
    PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY,
    attempt_block,
    perform_minion_action,
)
from vtesbot.engine.decision import Choice


def _fake_force_fail_provider_factory(*, exclude: bool = True):
    """Generic stand-in for Forced Confessional's own superior clause: a
    one-shot play (mirrors a real card going to the ash heap once played)
    offered to the actor, naming the currently-fixed `blocking_vampire` and
    optionally excluding it (the "cannot attempt to block this action
    again" half -- separable here to prove the force-fail half alone,
    `exclude=False`)."""
    used = [False]

    def provider(state, context):
        del state
        if used[0]:
            return []
        blocking_vampire_id = context.get("blocking_vampire")
        if blocking_vampire_id is None:
            return []

        def _apply(s):
            del s
            used[0] = True
            if exclude:
                context["pending"].setdefault(PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY, set()).add(
                    blocking_vampire_id
                )

        return [
            hooks.HookOption(
                choice=Choice("force_fail", "Force this attempt to fail"), apply=_apply
            )
        ]

    return provider, used


def test_zero_regression_no_provider_registered_asks_no_extra_decision():
    """With nothing registered against `FORCE_BLOCK_ATTEMPT_FAILURE_HOOK`
    (every card and test before OQ-65), the reactive offer point's own
    `Decision` is byte-for-byte the pre-OQ-65 one."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    assert blocker.instance_id == "B1"
    defender.assert_exhausted()


def test_not_offered_before_a_block_candidate_is_fixed():
    """ "Only usable if a minion attempts to block": the hook is never
    offered at `attempt_block`'s own proactive top-of-loop point (no
    `blocking_vampire` context there) -- only once a specific blocker is
    already fixed, in `_duel_stealth_intercept`'s own reactive branch."""
    provider, used = _fake_force_fail_provider_factory()
    hooks.register(FORCE_BLOCK_ATTEMPT_FAILURE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)  # no ready vampire at all: no candidate ever gets fixed.
    game = builder.build()
    actor = ScriptedAgent("P1")  # no answers scripted: raises if ever asked anything.
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    assert used[0] is False
    actor.assert_exhausted()


def test_offered_even_while_already_failing_on_the_raw_numbers():
    """rules-auditor finding: `base_stealth=1` with intercept 0 and no
    intercept-boost provider means the candidate's attempt already fails on
    the raw numbers alone, before the actor would ever be consulted at all
    pre-fix. The actor must still be offered a chance to exclude this
    specific blocker from attempting to block this action again -- that
    half has nothing to do with whether the numbers already fail -- and a
    *different* vampire must remain a legal candidate afterward, with the
    excluded one gone from the choice set."""
    provider, used = _fake_force_fail_provider_factory(exclude=True)
    hooks.register(FORCE_BLOCK_ATTEMPT_FAILURE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1)
    p2.ready_vampire("B2", capacity=3, blood=1)
    game = builder.build()
    seen_decisions = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            seen_decisions.append(decision)
            return super().decide(observation, decision)

    actor = RecordingAgent("P1").expect("stealth_modifier", "force_fail")
    game.state.agents["P1"] = actor
    defender = RecordingAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # already fails: stealth 1 > intercept 0.
    # B1 is now excluded; B2 remains offered (declined here to end the test
    # cleanly -- the point under test is the choice set, not B2's own fate).
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=1)

    assert blocker is None
    assert used[0] is True
    block_decisions = [d for d in seen_decisions if d.kind == "block_attempt"]
    assert len(block_decisions) == 2
    second_choice_values = {c.value for c in block_decisions[1].choices}
    assert "block_with:B1" not in second_choice_values
    assert "block_with:B2" in second_choice_values
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_chosen_option_forces_the_current_attempt_to_fail_outright():
    """A block attempt that would otherwise succeed (intercept 0 >= stealth
    0, no modifiers at all) fails once the actor forces it, with no further
    chance for the defender to respond -- proving this bypasses the
    stealth/intercept comparison entirely rather than merely tilting it."""
    provider, used = _fake_force_fail_provider_factory(exclude=False)
    hooks.register(FORCE_BLOCK_ATTEMPT_FAILURE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1").expect("stealth_modifier", "force_fail")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    # Not excluded this time (exclude=False): B1 remains a legal candidate
    # on the retry, but the test ends the loop by declining a second
    # attempt, since only the single-attempt outcome is under test here.
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None  # forced failure, not a numbers-driven one.
    assert used[0] is True
    assert game.vampire("B1").locked is False  # a failed attempt never locks the blocker.
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_merged_into_the_same_decision_as_stealth_modifier():
    """When a `STEALTH_MODIFIER_HOOK` provider is also registered, both
    sets of choices are offered together in one `Decision` (mirrors
    `test_intercept_decrease.py`'s own "merged" proof) -- the actor picks
    the force-fail option specifically, proving it was genuinely offered
    alongside, not instead of, the other."""

    def stealth_provider(state, context):
        if context.get("player") != "P1":
            return []
        return [hooks.HookOption(choice=Choice("bump_stealth", "+1 stealth"), apply=lambda s: 1)]

    force_fail_provider, used = _fake_force_fail_provider_factory(exclude=True)
    hooks.register("stealth_modifier", stealth_provider)
    hooks.register(FORCE_BLOCK_ATTEMPT_FAILURE_HOOK, force_fail_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1").expect("stealth_modifier", "force_fail")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    assert used[0] is True
    actor.assert_exhausted()
    defender.assert_exhausted()  # excluded: no second block_attempt decision, B1 was the only one.


def test_excluding_the_named_blocker_bars_it_from_a_later_attempt_this_action():
    """The "cannot attempt to block this action again" half: a second,
    still-ready-unlocked vampire remains a legal candidate on the retry,
    but the forced-fail blocker is never offered again."""
    provider, used = _fake_force_fail_provider_factory(exclude=True)
    hooks.register(FORCE_BLOCK_ATTEMPT_FAILURE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1)
    p2.ready_vampire("B2", capacity=3, blood=1)
    game = builder.build()
    seen_decisions = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            seen_decisions.append(decision)
            return super().decide(observation, decision)

    actor = RecordingAgent("P1").expect("stealth_modifier", "force_fail")
    game.state.agents["P1"] = actor
    defender = RecordingAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # forced to fail; B1 excluded.
    defender.expect("block_attempt", "block_with:B2")  # still legal; succeeds normally.
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    assert blocker.instance_id == "B2"
    assert used[0] is True
    block_decisions = [d for d in seen_decisions if d.kind == "block_attempt"]
    assert len(block_decisions) == 2
    second_choice_values = {c.value for c in block_decisions[1].choices}
    assert "block_with:B1" not in second_choice_values
    assert "block_with:B2" in second_choice_values
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_end_to_end_through_perform_minion_action_resolves_unblocked():
    """Real call site proof: forcing the lone candidate's attempt to fail
    resolves the action unblocked through `perform_minion_action`'s own
    `resolve()` callback."""
    provider, used = _fake_force_fail_provider_factory(exclude=True)
    hooks.register(FORCE_BLOCK_ATTEMPT_FAILURE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    acting = game.vampire("V1")
    actor = ScriptedAgent("P1").expect("stealth_modifier", "force_fail")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender
    resolve_calls: list[bool] = []

    def resolve(pending):
        del pending
        resolve_calls.append(True)

    perform_minion_action(game.state, "P1", "P2", acting, base_stealth=0, resolve=resolve)

    assert resolve_calls == [True]  # unblocked: B1's forced failure left no further candidate.
    assert used[0] is True
    actor.assert_exhausted()
    defender.assert_exhausted()
