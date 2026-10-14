"""Acting-side intercept-decrease Action Modifiers (OQ-30,
`docs/OPEN_QUESTIONS.md`, resolved): `engine/action.py::attempt_block`
offers `INTERCEPT_DECREASE_HOOK` to the *actor* (never the defender), at the
top of its own retry loop -- before any blocking candidate is even chosen,
and again on every retry (OQ-11) -- independent of the `"stealth_modifier"`/
`"intercept_modifier"` "only when needed" ping-pong. A provider's `apply`
appends a persistent, action-scoped `ActiveInterceptDecrease` (a `delta`
plus a blocking-candidate `qualifies` predicate) to
`pending[PENDING_INTERCEPT_DECREASE_KEY]`; `_duel_stealth_intercept`
re-evaluates every recorded modifier against *whichever* candidate is
currently fixed, every time it runs.

OQ-31 (resolved -- Reading B, the project owner's own ruling): the same
hook is *also* offered reactively, inside `_duel_stealth_intercept`'s own
`else` branch, merged into the same `Decision` as `STEALTH_MODIFIER_HOOK`'s
own choices (`_ask_stealth_or_decrease`) -- a second opportunity, once a
specific blocking candidate is already fixed, alongside (not instead of)
OQ-30's own proactive one.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a trivial fake `INTERCEPT_DECREASE_HOOK` provider (not
Perfect Paragon, krcg 101387, or any of the other cards OQ-30 names --
those remain `card-implementer`'s job once this capability exists; Perfect
Paragon stays registered `blocked`/`OQ-30` until then).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import (
    INTERCEPT_DECREASE_HOOK,
    PENDING_INTERCEPT_DECREASE_KEY,
    ActiveInterceptDecrease,
    attempt_block,
    perform_minion_action,
)
from vtesbot.engine.decision import Choice


def _fake_decrease_provider_factory(*, delta: int = -1, qualifies_capacity_below: int = 2):
    """Generic stand-in for the OQ-30 card family's shared shape ("Allies and
    younger vampires get -1 intercept"): a one-shot play (mirrors a real
    card going to the ash heap once played) offered to the actor, whose
    `apply` stashes a persistent `ActiveInterceptDecrease` into `pending`
    rather than returning a one-shot delta. `qualifies_capacity_below`
    stands in for "younger than the acting vampire" using the generic
    `CryptCard.capacity` field already exposed by `ScenarioBuilder`, so this
    test does not need to special-case any real card's own wording."""
    used = [False]

    def provider(state, context):
        del state
        if used[0]:
            return []

        def _apply(s):
            del s
            used[0] = True
            modifiers = context["pending"].setdefault(PENDING_INTERCEPT_DECREASE_KEY, [])
            modifiers.append(
                ActiveInterceptDecrease(
                    delta=delta,
                    qualifies=lambda v: v.card.capacity < qualifies_capacity_below,
                )
            )

        return [
            hooks.HookOption(
                choice=Choice("play_fake_modifier", "Play fake modifier"), apply=_apply
            )
        ]

    return provider, used


def test_zero_regression_no_provider_registered_asks_no_extra_decision():
    """With nothing registered against `INTERCEPT_DECREASE_HOOK` (every
    existing test and every other card today), `attempt_block`'s new
    top-of-loop `offer_until_pass` call returns instantly with no decision
    raised -- byte-for-byte the pre-OQ-30 behaviour."""
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


def test_actor_can_activate_the_modifier_before_any_block_candidate_is_chosen():
    """The window fires, and is offered to the *actor*, at the very top of
    the loop -- before `defender`'s own candidate decision is even built.
    Activating it against a qualifying candidate (capacity 1 < 2) turns a
    would-have-succeeded block (base_stealth=0, default intercept 0) into a
    failed one (intercept decreased to -1)."""
    provider, _used = _fake_decrease_provider_factory()
    hooks.register(INTERCEPT_DECREASE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=1, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1").expect("intercept_decrease", "play_fake_modifier")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # fails: intercept -1 < stealth 0
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    assert game.vampire("B1").locked is False  # failed attempt never locks
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_decrease_only_applies_to_a_qualifying_candidate():
    """Zero-regression counterpart: the same activated modifier leaves a
    non-qualifying candidate (capacity 3, not < 2) completely unaffected --
    its block still succeeds at the default intercept 0 >= stealth 0."""
    provider, _used = _fake_decrease_provider_factory()
    hooks.register(INTERCEPT_DECREASE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B2", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1").expect("intercept_decrease", "play_fake_modifier")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B2")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    assert blocker.instance_id == "B2"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_persistent_modifier_re_evaluates_against_a_retried_blocks_different_candidate():
    """OQ-11: a modifier activated once, before any candidate exists, must
    keep re-applying correctly across a retried block attempt with a
    *different* candidate within the same action -- not just the candidate
    that happened to be fixed when it was activated. B1 qualifies (capacity
    1) and fails once decreased; the defender retries with B2 (capacity 3,
    does not qualify), which succeeds normally. The actor is never offered
    the hook again on the retry (the fake provider is one-shot, modelling a
    real card already spent) -- proving the activation persists via
    `pending`, not by being re-played."""
    provider, used = _fake_decrease_provider_factory()
    hooks.register(INTERCEPT_DECREASE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=1, blood=1)
    p2.ready_vampire("B2", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1").expect("intercept_decrease", "play_fake_modifier")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # fails: intercept -1 < stealth 0
    defender.expect("block_attempt", "block_with:B2")  # succeeds: intercept 0 >= stealth 0
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    assert blocker.instance_id == "B2"
    assert used[0] is True  # activated exactly once, not re-offered on the retry
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_matching_deltas_from_multiple_active_modifiers_stack():
    """Two independently-activated modifiers (two physical cards, same
    shape) both matching the same candidate must both contribute -- proving
    `pending[PENDING_INTERCEPT_DECREASE_KEY]` accumulates a list, not a
    single overwritten record."""

    def _make_provider():
        used = [False]

        def provider(state, context):
            del state
            if used[0]:
                return []

            def _apply(s):
                del s
                used[0] = True
                modifiers = context["pending"].setdefault(PENDING_INTERCEPT_DECREASE_KEY, [])
                modifiers.append(ActiveInterceptDecrease(delta=-1, qualifies=lambda v: True))

            return [
                hooks.HookOption(
                    choice=Choice("play_fake_modifier", "Play fake modifier"), apply=_apply
                )
            ]

        return provider

    hooks.register(INTERCEPT_DECREASE_HOOK, _make_provider())
    hooks.register(INTERCEPT_DECREASE_HOOK, _make_provider())
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("intercept_decrease", "play_fake_modifier")
    actor.expect("intercept_decrease", "play_fake_modifier")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # fails: intercept -2 < stealth 0
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_can_be_activated_even_when_the_defender_has_no_candidate_at_all():
    """Perfect Paragon's own on-file ruling ("[c]an be played any time
    during the action before resolution; a block attempt is not required")
    means the window must fire even when `attempt_block` is about to
    short-circuit to `None` with no block-attempt decision at all -- the
    actor still gets first refusal on activating the modifier (here,
    declining it) before that short-circuit."""
    provider, used = _fake_decrease_provider_factory()
    hooks.register(INTERCEPT_DECREASE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)  # no ready vampire at all
    game = builder.build()
    actor = ScriptedAgent("P1").expect("intercept_decrease", "pass")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    assert used[0] is False  # declined: never activated
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_end_to_end_through_perform_minion_action_feeds_the_blocked_branch():
    """Real call site proof: the activated modifier still correctly decides
    a block attempt reached via `perform_minion_action`, and the shared
    `pending` dict it was recorded into survives (unused by anything else)
    into `on_blocked`."""
    provider, _used = _fake_decrease_provider_factory()
    hooks.register(INTERCEPT_DECREASE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=1, blood=0)
    game = builder.build()
    acting = game.vampire("V1")
    actor = ScriptedAgent("P1")
    actor.expect("intercept_decrease", "play_fake_modifier")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # fails: intercept -1 < stealth 0
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    resolve_calls: list[bool] = []

    def resolve(pending):
        del pending
        resolve_calls.append(True)

    perform_minion_action(game.state, "P1", "P2", acting, base_stealth=0, resolve=resolve)

    assert resolve_calls == [True]  # unblocked: the failed-then-declined attempt never connects
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_the_defender_never_sees_the_activated_modifiers_qualifies_predicate():
    """`rules-auditor` finding on this entry's first landing (CLAUDE.md
    "Information hiding"): once the actor activates an `ActiveInterceptDecrease`,
    it lives in `pending[PENDING_INTERCEPT_DECREASE_KEY]` -- the same shared
    `pending` object threaded into the `"intercept_modifier"`/
    "stealth_modifier"` hook context the ping-pong offers to *both* players.
    Neither player's own `Decision.context`, across the whole attempt, may
    carry `"pending"` (or any `Callable`, which `qualifies` itself is) --
    `attempt_block`/`_duel_stealth_intercept`/`hooks.offer_until_pass` must
    build every `Decision.context` via `hooks.sanitize_decision_context`,
    not a bare `dict(context)`."""

    def intercept_bump_provider(state, context):
        if context.get("player") != "P2":
            return []
        return [hooks.HookOption(choice=Choice("bump", "+5 intercept"), apply=lambda s: 5)]

    provider, _used = _fake_decrease_provider_factory()
    hooks.register(INTERCEPT_DECREASE_HOOK, provider)
    hooks.register("intercept_modifier", intercept_bump_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=1, blood=1)
    game = builder.build()
    seen_contexts: list[dict] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            seen_contexts.append(decision.context)
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("intercept_decrease", "play_fake_modifier")
    game.state.agents["P1"] = actor
    defender = RecordingAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("intercept_modifier", "bump")  # overcomes the decrease: -1 + 5 >= stealth 0
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None  # proves the modifiers really were live and consulted
    assert seen_contexts  # at least one Decision.context was captured
    for context in seen_contexts:
        assert "pending" not in context
        for value in context.values():
            assert not callable(value), f"Decision.context leaked a callable: {value!r}"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_actor_may_decline_proactively_and_still_play_the_modifier_reactively():
    """OQ-31 (resolved -- Reading B): the proactive, top-of-retry-loop
    offer is not the actor's only chance. The actor explicitly declines it
    before any candidate is even chosen, the defender's first (and only)
    candidate would otherwise succeed outright (base_stealth=0, default
    intercept 0), and the actor only activates the *same* modifier
    reactively once that specific candidate is already fixed -- turning the
    would-have-succeeded block into a failure. The reactive offer shares
    `STEALTH_MODIFIER_HOOK`'s own `"stealth_modifier"` decision kind
    (`_ask_stealth_or_decrease`), not `"intercept_decrease"`."""
    provider, used = _fake_decrease_provider_factory()
    hooks.register(INTERCEPT_DECREASE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=1, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("intercept_decrease", "pass")  # declines the proactive offer
    actor.expect("stealth_modifier", "play_fake_modifier")  # uses it reactively instead
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    # Would otherwise have succeeded at once (intercept 0 >= stealth 0);
    # the reactive decrease (-1) flips it to a failure -- re-offered, then
    # declined to end the test cleanly. The proactive offer is not asked
    # again on the retry: the provider is already used.
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    assert used[0] is True
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_reactive_offer_is_merged_with_stealth_modifier_into_one_decision():
    """When both a `"stealth_modifier"` provider and an `INTERCEPT_DECREASE_
    HOOK` provider are registered, the reactive point offers *both* sets of
    choices in the same `Decision` (`_ask_stealth_or_decrease`, mirroring
    `engine/combat.py::_ask_strike`'s own two-hooks-into-one-offer
    precedent) -- the actor picks the decrease option specifically, proving
    it was genuinely offered alongside, not instead of, the stealth option."""

    def stealth_provider(state, context):
        if context.get("player") != "P1":
            return []
        return [hooks.HookOption(choice=Choice("bump_stealth", "+1 stealth"), apply=lambda s: 1)]

    provider, used = _fake_decrease_provider_factory()
    hooks.register("stealth_modifier", stealth_provider)
    hooks.register(INTERCEPT_DECREASE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=1, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("intercept_decrease", "pass")  # declines the proactive offer
    actor.expect("stealth_modifier", "play_fake_modifier")  # picks the merged-in decrease choice
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None  # intercept -1 < stealth 0: the decrease was applied, not the +1 stealth
    assert used[0] is True
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_zero_regression_reactive_point_unaffected_when_no_decrease_provider_registered():
    """With no `INTERCEPT_DECREASE_HOOK` provider registered (every card and
    test before OQ-31), the reactive point's `Decision` is byte-for-byte the
    pre-OQ-31 `"stealth_modifier"` one: same kind, same single option, same
    outcome."""

    def stealth_provider(state, context):
        if context.get("player") != "P1":
            return []
        return [hooks.HookOption(choice=Choice("bump_stealth", "+1 stealth"), apply=lambda s: 1)]

    hooks.register("stealth_modifier", stealth_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1").expect("stealth_modifier", "bump_stealth")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")  # no intercept provider to try again with
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    actor.assert_exhausted()
    defender.assert_exhausted()
