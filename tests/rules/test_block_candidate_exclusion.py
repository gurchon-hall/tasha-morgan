"""`BLOCK_CANDIDATE_EXCLUSION_HOOK` (`engine/action.py`): the subtractive
sibling of `BLOCK_CANDIDATE_INJECTION_HOOK`. Offered to the *actor* at the
same proactive point in `attempt_block`'s retry loop as
`INTERCEPT_DECREASE_HOOK`/`STEALTH_INCREASE_HOOK` ("as the action is
announced", Rulebook §4), before the defender's block-candidate list is
computed at all. A chosen option's `apply` adds the target vampire's own
`instance_id` to `pending[PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY]`; the
candidate-list construction step then filters `ready_unlocked_vampires`
against that set, every pass through the retry loop.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a trivial fake provider -- `cards/seduction.py` (krcg
101712) and `cards/sleeping_mind.py` (krcg 101805), which name this gap,
remain `card-implementer`'s job once this capability exists; both stay
registered `blocked` until then.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import (
    BLOCK_CANDIDATE_EXCLUSION_HOOK,
    BLOCK_CANDIDATE_INJECTION_HOOK,
    PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY,
    WAKE_LOCKED_MINION_HOOK,
    attempt_block,
    perform_minion_action,
)
from vtesbot.engine.decision import Choice


def _exclude_provider_for(target_instance_id: str):
    """Generic stand-in for Seduction's/Sleeping Mind's own "choose a
    vampire; it cannot block this action" clause: offers the actor a
    one-shot option naming `target_instance_id`, mirroring a real card going
    to the ash heap once played."""

    def provider(state, context):
        del state
        pending = context["pending"]
        if target_instance_id in pending.get(PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY, set()):
            return []

        def apply(s):
            del s
            pending.setdefault(PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY, set()).add(target_instance_id)

        return [
            hooks.HookOption(
                choice=Choice(f"exclude:{target_instance_id}", f"Exclude {target_instance_id}"),
                apply=apply,
            )
        ]

    return provider


def test_hook_fires_for_the_actor_before_candidates_are_computed():
    """Queried even though the defender (P2) has zero vampires at all --
    strictly before `attempt_block`'s own "nothing legal to block with: no
    vacuous decision raised" short-circuit, which would otherwise return
    `None` without ever consulting this hook."""
    calls: list[str] = []

    def provider(state, context):
        del state
        calls.append(context["player"])
        return []

    hooks.register(BLOCK_CANDIDATE_EXCLUSION_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    game.state.agents["P1"] = ScriptedAgent("P1")  # provider offers nothing: no decision
    game.state.agents["P2"] = ScriptedAgent("P2")

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    assert calls == ["P1"]


def test_choosing_to_exclude_a_candidate_removes_it_from_the_block_candidate_list():
    """The excluded vampire is never even offered as a choice -- not merely
    one the defender declines -- proving this is a candidate-list filter,
    not a stealth/intercept penalty."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1)
    p2.ready_vampire("B2", capacity=3, blood=1)
    game = builder.build()
    hooks.register(BLOCK_CANDIDATE_EXCLUSION_HOOK, _exclude_provider_for("B1"))
    seen_decisions = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            seen_decisions.append(decision)
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("block_candidate_exclusion", "exclude:B1")
    game.state.agents["P1"] = actor
    defender = RecordingAgent("P2")
    defender.expect("block_attempt", "block_with:B2")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    assert blocker.instance_id == "B2"
    block_decision = next(d for d in seen_decisions if d.kind == "block_attempt")
    choice_values = {c.value for c in block_decision.choices}
    assert "block_with:B1" not in choice_values
    assert "block_with:B2" in choice_values
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_exclusion_persists_across_a_retried_failed_attempt():
    """Mirrors ENG-005's precedent for `INTERCEPT_DECREASE_HOOK`: a failed
    block attempt loops `attempt_block` back to the top of its retry loop,
    where the exclusion filter is recomputed fresh -- the excluded vampire
    must never reappear as a candidate on the retry either."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1)
    p2.ready_vampire("B3", capacity=3, blood=1)
    game = builder.build()
    hooks.register(BLOCK_CANDIDATE_EXCLUSION_HOOK, _exclude_provider_for("B1"))
    seen_decisions = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            seen_decisions.append(decision)
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("block_candidate_exclusion", "exclude:B1")
    game.state.agents["P1"] = actor
    defender = RecordingAgent("P2")
    defender.expect("block_attempt", "block_with:B3")  # fails: stealth 1 > intercept 0
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=1)

    assert blocker is None
    block_decisions = [d for d in seen_decisions if d.kind == "block_attempt"]
    assert len(block_decisions) == 2
    for decision in block_decisions:
        assert "block_with:B1" not in {c.value for c in decision.choices}
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_exclusion_survives_a_later_wake_locked_minion_hook_making_the_same_vampire_eligible():
    """`cards/sleeping_mind.py`'s own docstring: the exclusion is checked
    *after* `WAKE_LOCKED_MINION_HOOK` (ENG-030) has had its chance to set
    `woken` -- naming a locked vampire here specifically vetoes any such
    wake-based attempt for that one vampire, for the rest of the action."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, locked=True)
    game = builder.build()

    def wake_provider(state, context):
        if context["player"] != "P2":
            return []
        b1 = state.players["P2"].vampires["B1"]
        if b1.woken:
            return []

        def apply(s):
            del s
            b1.woken = True

        return [hooks.HookOption(choice=Choice("wake_b1", "Wake B1"), apply=apply)]

    hooks.register(BLOCK_CANDIDATE_EXCLUSION_HOOK, _exclude_provider_for("B1"))
    hooks.register(WAKE_LOCKED_MINION_HOOK, wake_provider)
    actor = ScriptedAgent("P1").expect("block_candidate_exclusion", "exclude:B1")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("wake_locked_minion", "wake_b1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None  # excluded despite being woken: no candidate at all
    assert game.vampire("B1").woken is True  # the wake itself still happened
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_zero_regression_ordinary_block_path_unaffected_when_no_provider_registered():
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


def _injection_provider_for(target_instance_id: str):
    """Generic stand-in for Second Tradition: Domain's/Organized
    Resistance's own "unlock a locked vampire you control; it attempts to
    block" shape, parameterized by which vampire it targets -- mirrors
    `_exclude_provider_for`'s own shape."""

    def injection_provider(state, context):
        del state

        def apply(s):
            vampire = s.players[context["defender"]].vampires[target_instance_id]
            vampire.locked = False
            return vampire

        return [
            hooks.HookOption(
                choice=Choice(
                    f"forced_block:{target_instance_id}",
                    f"Unlock and force-block with {target_instance_id}",
                ),
                apply=apply,
                block_candidate_instance_id=target_instance_id,
            )
        ]

    return injection_provider


def test_zero_regression_coexists_with_block_candidate_injection_hook():
    """Zero-interaction check: an unrelated `BLOCK_CANDIDATE_INJECTION_HOOK`
    provider (ENG-018) is unaffected by, and does not interact with, the
    exclusion set -- the two hooks pull from disjoint candidate pools
    (ready-unlocked filtered-out vs. injected-from-locked)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1, locked=True)
    p2.ready_vampire("B2", capacity=3, blood=0, locked=True)
    game = builder.build()
    hooks.register(BLOCK_CANDIDATE_EXCLUSION_HOOK, _exclude_provider_for("B1"))
    hooks.register(BLOCK_CANDIDATE_INJECTION_HOOK, _injection_provider_for("B2"))
    actor = ScriptedAgent("P1").expect("block_candidate_exclusion", "exclude:B1")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2").expect("block_attempt", "forced_block:B2")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=5)

    assert blocker is not None
    assert blocker.instance_id == "B2"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_injected_candidate_targeting_the_same_excluded_vampire_is_filtered_out():
    """The previously-blind case (rules-auditor finding): a
    `BLOCK_CANDIDATE_INJECTION_HOOK` provider (e.g. Second Tradition:
    Domain, Organized Resistance) targets the *same* vampire a
    `BLOCK_CANDIDATE_EXCLUSION_HOOK` option just excluded (e.g. Sleeping
    Mind). The injected option naming B1 must never be offered, nor ever
    resolve as the blocker -- excluding B1 must mean B1 cannot block this
    action by any means, hardcoded or injected."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1, locked=True)
    game = builder.build()
    hooks.register(BLOCK_CANDIDATE_EXCLUSION_HOOK, _exclude_provider_for("B1"))
    hooks.register(BLOCK_CANDIDATE_INJECTION_HOOK, _injection_provider_for("B1"))
    actor = ScriptedAgent("P1").expect("block_candidate_exclusion", "exclude:B1")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")  # B1 was the only candidate, now filtered: no decision at all
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=5)

    assert blocker is None
    assert game.vampire("B1").locked is True  # never unlocked: the injected apply never ran
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_end_to_end_through_perform_minion_action_excludes_the_named_vampire():
    """Real call site proof: excluding the defender's only vampire leaves
    nothing to block with -- the action resolves unblocked through
    `perform_minion_action`'s own `resolve()` callback."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    acting = game.vampire("V1")
    hooks.register(BLOCK_CANDIDATE_EXCLUSION_HOOK, _exclude_provider_for("B1"))
    actor = ScriptedAgent("P1").expect("block_candidate_exclusion", "exclude:B1")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")  # B1 was the only vampire, now excluded: no decision at all
    game.state.agents["P2"] = defender
    resolve_calls: list[bool] = []

    def resolve(pending):
        del pending
        resolve_calls.append(True)

    perform_minion_action(game.state, "P1", "P2", acting, base_stealth=0, resolve=resolve)

    assert resolve_calls == [True]
    actor.assert_exhausted()
    defender.assert_exhausted()
