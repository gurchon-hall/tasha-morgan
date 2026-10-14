"""The generic card-hook dispatcher (`engine/hooks.py`, CLAUDE.md milestone-3
scaffolding pass) and its wiring into the block-attempt stealth/intercept
ping-pong (`engine/action.py`).

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism* (CLAUDE.md "Card hooks") using trivial fake providers, not a
real card -- real card effect modules and their own tests are
`card-implementer`'s next pass.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import attempt_block


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


def test_run_effects_calls_every_registered_provider_with_context():
    """Positive-path proof for `hooks.run_effects` (CLAUDE.md rule 3's
    "mandatory effects" exception -- a provider's own effect *is* the
    mutation, no `Decision`, no aggregated return value): every registered
    provider actually runs, once, with the context `run_effects` was called
    with. `run_effects` has no return value to assert on directly (unlike
    `sum_modifiers`/`union_modifiers`), so each fake provider appends to a
    shared, mutable list instead, mirroring `test_sum_modifiers_adds_every_
    registered_providers_contribution`'s pattern."""
    calls: list[tuple[str, int]] = []

    def provider_a(state, context):
        calls.append(("a", context["votes_for"]))

    def provider_b(state, context):
        calls.append(("b", context["votes_for"]))

    hooks.register("fake_effects", provider_a)
    hooks.register("fake_effects", provider_b)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()

    hooks.run_effects("fake_effects", game.state, votes_for=3)

    assert calls == [("a", 3), ("b", 3)]


def test_run_effects_is_a_safe_no_op_with_no_providers_registered():
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()

    hooks.run_effects("fake_effects_unused", game.state, votes_for=1)  # must not raise


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


def test_sanitize_decision_context_strips_pending_but_keeps_everything_else():
    """Direct unit test of the helper itself (`rules-auditor` finding, OQ-30,
    `docs/OPEN_QUESTIONS.md`): `"pending"` is removed, every other key is
    passed through unchanged, and the input `context` is not mutated."""
    context = {"actor": "P1", "pending": {"stashed": object()}, "action": "bleed"}

    sanitized = hooks.sanitize_decision_context(context)

    assert sanitized == {"actor": "P1", "action": "bleed"}
    assert "pending" in context  # the input mapping itself is untouched


def test_offer_until_pass_never_exposes_pending_in_the_decisions_context():
    """`rules-auditor` finding (OQ-30): `offer_until_pass` must build
    `Decision.context` via `sanitize_decision_context`, not a bare
    `dict(context)` -- the provider itself still receives the full
    `context` (including `pending`), only the agent-visible `Decision`
    must not."""
    from vtesbot.engine.decision import Choice

    seen_by_provider = {}

    def provider(state, context):
        seen_by_provider.update(context)
        return [hooks.HookOption(choice=Choice("tick", "Tick"), apply=lambda s: None)]

    hooks.register("fake_loop_pending", provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    seen_contexts = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            seen_contexts.append(decision.context)
            return super().decide(observation, decision)

    agent = RecordingAgent("P1")
    agent.expect("fake_loop_pending", "pass")
    game.state.agents["P1"] = agent

    live_pending = {"stashed": 1}
    hooks.offer_until_pass(game.state, "fake_loop_pending", "P1", context={"pending": live_pending})

    assert seen_by_provider["pending"] is live_pending  # provider still gets the real object
    assert all("pending" not in ctx for ctx in seen_contexts)  # agent never does
    agent.assert_exhausted()


def test_resolve_impulse_window_never_exposes_pending_in_the_decisions_context():
    """Same `rules-auditor` finding (OQ-30) for the two-sided impulse window."""
    from vtesbot.engine.decision import Choice

    def provider(state, context):
        if context.get("player") != "P1":
            return []
        return [hooks.HookOption(choice=Choice("tick", "Tick"), apply=lambda s: None)]

    hooks.register("fake_window_pending", provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    seen_contexts = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            seen_contexts.append(decision.context)
            return super().decide(observation, decision)

    p1 = RecordingAgent("P1")
    p1.expect("fake_window_pending", "pass")
    p2 = ScriptedAgent("P2")
    game.state.agents["P1"] = p1
    game.state.agents["P2"] = p2

    hooks.resolve_impulse_window(
        game.state, "fake_window_pending", "P1", "P2", context={"pending": {"stashed": 1}}
    )

    assert all("pending" not in ctx for ctx in seen_contexts)
    p1.assert_exhausted()
    p2.assert_exhausted()


def test_apply_chosen_option_runs_apply_normally_with_no_cancel_provider():
    """Zero-regression check (`docs/OPEN_QUESTIONS.md` OQ-32, resolved): with
    no `CANCEL_AS_PLAYED_HOOK` provider registered (true of every card in
    the pool today), `offer_until_pass` behaves byte-for-byte as before this
    primitive existed -- no extra decision is raised to the other player."""
    from vtesbot.engine.decision import Choice

    calls = []

    def provider(state, context):
        return [
            hooks.HookOption(choice=Choice("tick", "Tick"), apply=lambda s: calls.append("apply"))
        ]

    hooks.register("fake_cancelable", provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    p1 = ScriptedAgent("P1")
    p1.expect("fake_cancelable", "tick")
    p1.expect("fake_cancelable", "pass")
    p2 = ScriptedAgent("P2")  # never asked: no CANCEL_AS_PLAYED_HOOK provider exists.
    game.state.agents["P1"] = p1
    game.state.agents["P2"] = p2

    hooks.offer_until_pass(game.state, "fake_cancelable", "P1", context={})

    assert calls == ["apply"]
    p1.assert_exhausted()
    p2.assert_exhausted()


def test_apply_chosen_option_pays_cost_but_suppresses_apply_when_canceled():
    """The actual OQ-32 mechanism: the other side cancels a chosen option
    *as it is played* -- its `cost` (the generic "cost is still paid") still
    runs, but its `apply` (the actual effect) is suppressed, and the
    canceling option's own `apply` (its own cost, e.g. Diana's "burn 1
    blood") runs instead. Proven generically, against a throwaway fake
    hook/provider pair -- not coupled to Diana Iadanza's own card module,
    which this primitive does not implement (`src/vtesbot/cards/
    diana_iadanza.py` stays `blocked`, pending a `card-implementer` pass)."""
    from vtesbot.engine.decision import Choice

    paid_cost = []
    ran_effect = []
    canceler_paid = []

    def provider(state, context):
        return [
            hooks.HookOption(
                choice=Choice("tick", "Tick"),
                cost=lambda s: paid_cost.append(True),
                apply=lambda s: ran_effect.append(True),
            )
        ]

    def cancel_provider(state, context):
        assert context["canceled_choice"] == "tick"
        assert context["canceled_by"] == "P1"
        return [
            hooks.HookOption(
                choice=Choice("cancel_it", "Cancel as played"),
                apply=lambda s: canceler_paid.append(True),
            )
        ]

    hooks.register("fake_cancelable", provider)
    hooks.register(hooks.CANCEL_AS_PLAYED_HOOK, cancel_provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    p1 = ScriptedAgent("P1")
    p1.expect("fake_cancelable", "tick")
    p1.expect("fake_cancelable", "pass")  # nothing left after the suppressed option
    p2 = ScriptedAgent("P2")
    p2.expect(hooks.CANCEL_AS_PLAYED_HOOK, "cancel_it")
    game.state.agents["P1"] = p1
    game.state.agents["P2"] = p2

    hooks.offer_until_pass(game.state, "fake_cancelable", "P1", context={})

    assert paid_cost == [True]  # "cost is still paid"
    assert ran_effect == []  # the effect itself is suppressed
    assert canceler_paid == [True]  # the canceling option's own cost ran instead
    p1.assert_exhausted()
    p2.assert_exhausted()


def test_apply_chosen_option_passing_the_cancellation_lets_apply_run():
    """The other side is offered a cancellation but declines (passes): the
    original option's own `apply` runs normally, same as if no
    `CANCEL_AS_PLAYED_HOOK` provider had been registered at all."""
    from vtesbot.engine.decision import Choice

    ran_effect = []

    def provider(state, context):
        return [
            hooks.HookOption(choice=Choice("tick", "Tick"), apply=lambda s: ran_effect.append(True))
        ]

    def cancel_provider(state, context):
        return [
            hooks.HookOption(choice=Choice("cancel_it", "Cancel as played"), apply=lambda s: None)
        ]

    hooks.register("fake_cancelable", provider)
    hooks.register(hooks.CANCEL_AS_PLAYED_HOOK, cancel_provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    p1 = ScriptedAgent("P1")
    p1.expect("fake_cancelable", "tick")
    p1.expect("fake_cancelable", "pass")
    p2 = ScriptedAgent("P2")
    p2.expect(hooks.CANCEL_AS_PLAYED_HOOK, "pass")
    game.state.agents["P1"] = p1
    game.state.agents["P2"] = p2

    hooks.offer_until_pass(game.state, "fake_cancelable", "P1", context={})

    assert ran_effect == [True]
    p1.assert_exhausted()
    p2.assert_exhausted()


def test_apply_chosen_option_is_offered_to_the_non_acting_side_in_an_impulse_window():
    """Same mechanism through `resolve_impulse_window` (the other generic
    decision-loop helper): whichever side did *not* just choose gets offered
    the cancellation -- here, the acting player's own chosen option is
    offered for cancellation to the non-acting player."""
    from vtesbot.engine.decision import Choice

    used = [False]
    ran_effect = []

    def provider(state, context):
        # One-shot, like a real card: `cost` (below) marks it used the
        # instant it is chosen, regardless of whether it then gets
        # canceled -- same "still treated as played" semantics the OQ-32
        # docstring documents, needed here only so the window terminates.
        if context.get("player") != "P1" or used[0]:
            return []
        return [
            hooks.HookOption(
                choice=Choice("tick", "Tick"),
                cost=lambda s: used.__setitem__(0, True),
                apply=lambda s: ran_effect.append(True),
            )
        ]

    def cancel_provider(state, context):
        assert context["canceled_by"] == "P1"
        return [
            hooks.HookOption(choice=Choice("cancel_it", "Cancel as played"), apply=lambda s: None)
        ]

    hooks.register("fake_window", provider)
    hooks.register(hooks.CANCEL_AS_PLAYED_HOOK, cancel_provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    p1 = ScriptedAgent("P1")
    p1.expect("fake_window", "tick")
    p2 = ScriptedAgent("P2")
    p2.expect(hooks.CANCEL_AS_PLAYED_HOOK, "cancel_it")
    game.state.agents["P1"] = p1
    game.state.agents["P2"] = p2

    hooks.resolve_impulse_window(game.state, "fake_window", "P1", "P2", context={})

    assert ran_effect == []
    p1.assert_exhausted()
    p2.assert_exhausted()


def test_cancel_context_carries_the_canceled_options_played_card_type():
    """`docs/OPEN_QUESTIONS.md` OQ-33, resolved: a `CANCEL_AS_PLAYED_HOOK`
    provider that only cancels a specific card type (Diana Iadanza's own
    "cancel a *reaction card* as it is played") can gate on
    `context["canceled_card_type"]` instead of fragile `canceled_choice`
    string-matching. Here the fake provider's own option is marked
    `played_card_type="Reaction"`, and the canceler checks for exactly
    that -- proving the marker reaches the cancel provider's context and is
    load-bearing, not merely present."""
    from vtesbot.engine.decision import Choice

    ran_effect = []
    canceler_ran = []

    def provider(state, context):
        return [
            hooks.HookOption(
                choice=Choice("tick", "Tick"),
                apply=lambda s: ran_effect.append(True),
                played_card_type="Reaction",
            )
        ]

    def cancel_provider(state, context):
        if context["canceled_card_type"] != "Reaction":
            return []  # mirrors Diana Iadanza's own "a reaction card" gate.
        return [
            hooks.HookOption(
                choice=Choice("cancel_it", "Cancel as played"),
                apply=lambda s: canceler_ran.append(True),
            )
        ]

    hooks.register("fake_cancelable", provider)
    hooks.register(hooks.CANCEL_AS_PLAYED_HOOK, cancel_provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    p1 = ScriptedAgent("P1")
    p1.expect("fake_cancelable", "tick")
    p1.expect("fake_cancelable", "pass")
    p2 = ScriptedAgent("P2")
    p2.expect(hooks.CANCEL_AS_PLAYED_HOOK, "cancel_it")
    game.state.agents["P1"] = p1
    game.state.agents["P2"] = p2

    hooks.offer_until_pass(game.state, "fake_cancelable", "P1", context={})

    assert ran_effect == []  # the reaction-only canceler correctly suppressed it
    assert canceler_ran == [True]
    p1.assert_exhausted()
    p2.assert_exhausted()


def test_a_reaction_only_canceler_cannot_reach_a_non_card_play_option():
    """The motivating OQ-33 scenario itself: a `CANCEL_AS_PLAYED_HOOK`
    provider gated to Reaction cards only must offer nothing at all against
    an option that is not a card play (`played_card_type` left at its
    default `None` -- the same shape Modius's "discard a master card to get
    +1 vote" and Oxford University, England's polling-step burn both use).
    Proven generically here, not against either real card module."""
    from vtesbot.engine.decision import Choice

    ran_effect = []

    def provider(state, context):
        return [
            hooks.HookOption(
                choice=Choice("tick", "Tick"),
                apply=lambda s: ran_effect.append(True),
                # `played_card_type` left at its default `None`: an ability
                # activation, not a card being played (module docstring).
            )
        ]

    def cancel_provider(state, context):
        if context["canceled_card_type"] != "Reaction":
            return []  # mirrors Diana Iadanza's own "a reaction card" gate.
        raise AssertionError("must never offer a cancellation for a non-Reaction option")

    hooks.register("fake_cancelable", provider)
    hooks.register(hooks.CANCEL_AS_PLAYED_HOOK, cancel_provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    p1 = ScriptedAgent("P1")
    p1.expect("fake_cancelable", "tick")
    p1.expect("fake_cancelable", "pass")
    p2 = ScriptedAgent("P2")  # never asked: the reaction-only canceler offers nothing.
    game.state.agents["P1"] = p1
    game.state.agents["P2"] = p2

    hooks.offer_until_pass(game.state, "fake_cancelable", "P1", context={})

    assert ran_effect == [True]  # not suppressed: no legal cancellation was ever offered
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


def test_run_effects_stops_calling_providers_once_the_game_is_over():
    """Rulebook SS5 Ending the Game: once an oust ends the game, no later
    provider may keep mutating state."""
    from vtesbot.engine.pool import lose_pool

    calls: list[str] = []

    def ousting_provider(state, context):
        calls.append("ousting")
        lose_pool(state, "P1", 1)

    def later_provider(state, context):
        calls.append("later")

    hooks.register("fake_effects_over", ousting_provider)
    hooks.register("fake_effects_over", later_provider)
    game = ScenarioBuilder(seed=1).player("P1", pool=1).player("P2", pool=30).build()

    hooks.run_effects("fake_effects_over", game.state)

    assert game.state.game_over is True
    assert calls == ["ousting"]
