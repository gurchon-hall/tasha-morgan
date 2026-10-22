"""Acting-side stealth-increase Action Modifiers (RUL-011, resolved):
`engine/action.py::attempt_block` offers `STEALTH_INCREASE_HOOK` to the *actor*
(never the defender), at the top of its own retry loop -- before any blocking
candidate is even chosen, and again on every retry (ENG-005) -- independent of
the `"stealth_modifier"`/`"intercept_modifier"` "only when needed" ping-pong.
`INTERCEPT_DECREASE_HOOK`'s own sibling (ENG-021/RUL-009): a provider's `apply`
appends a persistent, action-scoped `ActiveStealthIncrease` (a bare `delta`,
never candidate- dependent -- unlike `ActiveInterceptDecrease`, there is no
blocking candidate for a stealth value to qualify against) to
`pending[PENDING_STEALTH_INCREASE_KEY]`; `_duel_stealth_intercept` folds every
recorded delta into its own `stealth` baseline fresh, every time it runs.

The same hook is *also* offered reactively, inside `_duel_stealth_
intercept`'s own `else` branch, merged into the same `Decision` as
`STEALTH_MODIFIER_HOOK`'s (and `INTERCEPT_DECREASE_HOOK`'s) own choices
(`_ask_stealth_or_modifier`) -- a second opportunity, once a specific
blocking candidate is already fixed, alongside (not instead of) the
proactive one.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a trivial fake `STEALTH_INCREASE_HOOK` provider (not
Loup, krcg 102273 -- see `tests/cards/test_loup.py` for that card's own
tests against the real provider).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import (
    PENDING_STEALTH_INCREASE_KEY,
    STEALTH_INCREASE_HOOK,
    ActiveStealthIncrease,
    attempt_block,
)
from vtesbot.engine.decision import Choice


def _fake_increase_provider_factory(*, delta: int = 1):
    """Generic stand-in for the RUL-011 shape ("get +N stealth"): a one-shot
    play (mirrors a real card going to the ash heap, or a standing grant
    being activated, once) offered to the actor, whose `apply` stashes a
    persistent `ActiveStealthIncrease` into `pending` rather than returning
    a one-shot delta."""
    used = [False]

    def provider(state, context):
        del state
        if used[0]:
            return []

        def _apply(s):
            del s
            used[0] = True
            modifiers = context["pending"].setdefault(PENDING_STEALTH_INCREASE_KEY, [])
            modifiers.append(ActiveStealthIncrease(delta=delta))

        return [
            hooks.HookOption(
                choice=Choice("play_fake_modifier", "Play fake modifier"), apply=_apply
            )
        ]

    return provider, used


def test_zero_regression_no_provider_registered_asks_no_extra_decision():
    """With nothing registered against `STEALTH_INCREASE_HOOK` (every
    existing test and every other card today), `attempt_block`'s new
    top-of-loop `offer_until_pass` call returns instantly with no decision
    raised -- byte-for-byte the pre-RUL-011 behaviour."""
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
    Activating it (default intercept 0) turns a would-have-succeeded block
    (base_stealth=0) into a failed one (stealth increased to 1)."""
    provider, _used = _fake_increase_provider_factory()
    hooks.register(STEALTH_INCREASE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=1, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1").expect("stealth_increase", "play_fake_modifier")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # fails: stealth 1 > intercept 0
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    assert game.vampire("B1").locked is False  # failed attempt never locks
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_persistent_modifier_applies_identically_across_a_retried_blocks_different_candidate():
    """ENG-005: a modifier activated once, before any candidate exists, is
    never candidate-dependent (unlike `ActiveInterceptDecrease`) -- it must
    keep applying identically across a retried block attempt with a
    *different* candidate within the same action. Both B1 and B2 fail to
    block once the actor's stealth is increased to 1 (both default
    intercept 0). The actor is never offered the hook again on the retry
    (the fake provider is one-shot, modelling a real card already spent) --
    proving the activation persists via `pending`, not by being re-played."""
    provider, used = _fake_increase_provider_factory()
    hooks.register(STEALTH_INCREASE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=1, blood=1)
    p2.ready_vampire("B2", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1").expect("stealth_increase", "play_fake_modifier")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # fails: stealth 1 > intercept 0
    defender.expect("block_attempt", "block_with:B2")  # also fails: same reason
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    assert used[0] is True  # activated exactly once, not re-offered on the retry
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_matching_deltas_from_multiple_active_modifiers_stack():
    """Two independently-activated modifiers (two physical cards, same
    shape) must both contribute -- proving `pending[PENDING_STEALTH_
    INCREASE_KEY]` accumulates a list, not a single overwritten record."""

    def _make_provider():
        used = [False]

        def provider(state, context):
            del state
            if used[0]:
                return []

            def _apply(s):
                del s
                used[0] = True
                modifiers = context["pending"].setdefault(PENDING_STEALTH_INCREASE_KEY, [])
                modifiers.append(ActiveStealthIncrease(delta=1))

            return [
                hooks.HookOption(
                    choice=Choice("play_fake_modifier", "Play fake modifier"), apply=_apply
                )
            ]

        return provider

    hooks.register(STEALTH_INCREASE_HOOK, _make_provider())
    hooks.register(STEALTH_INCREASE_HOOK, _make_provider())
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("stealth_increase", "play_fake_modifier")
    actor.expect("stealth_increase", "play_fake_modifier")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # fails: stealth 2 > intercept 0
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_can_be_activated_even_when_the_defender_has_no_candidate_at_all():
    """Loup's own on-file ruling ("[c]an be used even if the stealth is not
    currently needed") means the window must fire even when `attempt_block`
    is about to short-circuit to `None` with no block-attempt decision at
    all -- the actor still gets first refusal on activating the modifier
    (here, declining it) before that short-circuit."""
    provider, used = _fake_increase_provider_factory()
    hooks.register(STEALTH_INCREASE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)  # no ready vampire at all
    game = builder.build()
    actor = ScriptedAgent("P1").expect("stealth_increase", "pass")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    assert used[0] is False  # declined: never activated
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_actor_may_decline_proactively_and_still_play_the_modifier_reactively():
    """The proactive, top-of-retry-loop offer is not the actor's only
    chance. The actor explicitly declines it before any candidate is even
    chosen, the defender's first (and only) candidate would otherwise
    succeed outright (base_stealth=0, default intercept 0), and the actor
    only activates the *same* modifier reactively once that specific
    candidate is already fixed -- turning the would-have-succeeded block
    into a failure. The reactive offer shares `STEALTH_MODIFIER_HOOK`'s own
    `"stealth_modifier"` decision kind (`_ask_stealth_or_modifier`), not
    `"stealth_increase"`."""
    provider, used = _fake_increase_provider_factory()
    hooks.register(STEALTH_INCREASE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=1, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("stealth_increase", "pass")  # declines the proactive offer
    actor.expect("stealth_modifier", "play_fake_modifier")  # uses it reactively instead
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    # Would otherwise have succeeded at once (intercept 0 >= stealth 0); the
    # reactive increase (+1) flips it to a failure -- re-offered, then
    # declined to end the test cleanly.
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    assert used[0] is True
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_reactive_offer_is_merged_with_stealth_modifier_and_intercept_decrease_into_one_decision():
    """When a `"stealth_modifier"` provider, an `INTERCEPT_DECREASE_HOOK`
    provider and a `STEALTH_INCREASE_HOOK` provider are all registered, the
    reactive point offers *all three* sets of choices in the same `Decision`
    (`_ask_stealth_or_modifier`) -- the actor picks the increase option
    specifically, proving it was genuinely offered alongside, not instead
    of, the other two."""
    from vtesbot.engine.action import (
        INTERCEPT_DECREASE_HOOK,
        PENDING_INTERCEPT_DECREASE_KEY,
        ActiveInterceptDecrease,
    )

    def stealth_provider(state, context):
        if context.get("player") != "P1":
            return []
        return [hooks.HookOption(choice=Choice("bump_stealth", "+1 stealth"), apply=lambda s: 1)]

    decrease_used = [False]

    def decrease_provider(state, context):
        del state
        if decrease_used[0]:
            return []

        def _apply(s):
            del s
            decrease_used[0] = True
            context["pending"].setdefault(PENDING_INTERCEPT_DECREASE_KEY, []).append(
                ActiveInterceptDecrease(delta=-1, qualifies=lambda v: True)
            )

        return [hooks.HookOption(choice=Choice("bump_decrease", "-1 intercept"), apply=_apply)]

    increase_provider, used = _fake_increase_provider_factory()
    hooks.register("stealth_modifier", stealth_provider)
    hooks.register(INTERCEPT_DECREASE_HOOK, decrease_provider)
    hooks.register(STEALTH_INCREASE_HOOK, increase_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=1, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("intercept_decrease", "pass")  # declines the proactive decrease offer
    actor.expect("stealth_increase", "pass")  # declines the proactive increase offer
    actor.expect("stealth_modifier", "play_fake_modifier")  # picks the merged-in increase choice
    # Block fails (stealth 1 > intercept 0): a retry re-offers the decrease
    # proactively (still unused, since the increase was picked instead).
    actor.expect("intercept_decrease", "pass")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None  # stealth 1 > intercept 0: the increase was applied
    assert used[0] is True
    assert decrease_used[0] is False  # never chosen, only ever offered
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_zero_regression_reactive_point_unaffected_when_no_increase_provider_registered():
    """With no `STEALTH_INCREASE_HOOK` provider registered (every card and
    test before RUL-011), the reactive point's `Decision` is byte-for-byte the
    pre-RUL-011 `"stealth_modifier"` one: same kind, same single option, same
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
