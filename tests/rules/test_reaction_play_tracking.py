"""Action-scoped Reaction-card play tracking: `hooks.mark_reaction_played`
records a chosen Reaction-type option into the action's own `pending` dict
(`hooks.PENDING_REACTION_PLAYED_KEY`) -- even if it is later canceled as
played ([LSJ 20070330]: a card canceled as it is played still counts as
having been played). Five call sites resolve a chosen Reaction-type
`HookOption` against an action-scoped `pending`: `hooks.apply_chosen_option`
itself (the choke point for `offer_until_pass`/`resolve_impulse_window`),
`engine/action.py::_ask_modifier`, `engine/action.py::
_ask_stealth_or_modifier`, `engine/action.py::attempt_block`'s
`BLOCK_CANDIDATE_INJECTION_HOOK` branch, and `engine/politics.py::
_cast_votes`'s mid-cast cancel-choice branch -- see `hooks.py`'s own
`mark_reaction_played` docstring. `engine/action.py::
perform_minion_action`'s own `ACTION_SUCCEEDED_HOOK` dispatch forwards
that same `pending` dict so a provider can read the flag;
`engine/politics.py::resolve_referendum` bridges its own local `pending`
(used for polling/tally) into the forwarded `action_pending` the same way
it already bridges `REFERENDUM_RESULT_KEY`.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using trivial fake providers -- `cards/perfectionist.py`
(krcg 101388), which names this gap, remains `card-implementer`'s job
once this capability exists; it stays registered `blocked` until then.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import (
    ACTION_POLITICAL,
    ACTION_SUCCEEDED_HOOK,
    BLOCK_CANDIDATE_INJECTION_HOOK,
    attempt_block,
    perform_minion_action,
)
from vtesbot.engine.decision import Choice
from vtesbot.engine.politics import POLITICAL_ACTION_STEALTH, POLLING_STEP_HOOK, resolve_referendum

# --- The choke point itself: apply_chosen_option / offer_until_pass --------


def test_apply_chosen_option_marks_reaction_play_when_applied_normally():
    def provider(state, context):
        del state, context
        return [
            hooks.HookOption(
                choice=Choice("tick", "Tick"), apply=lambda s: None, played_card_type="Reaction"
            )
        ]

    hooks.register("fake_reaction", provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    p1 = ScriptedAgent("P1")
    p1.expect("fake_reaction", "tick")
    p1.expect("fake_reaction", "pass")
    game.state.agents["P1"] = p1
    game.state.agents["P2"] = ScriptedAgent("P2")

    pending: dict = {}
    hooks.offer_until_pass(game.state, "fake_reaction", "P1", context={"pending": pending})

    assert pending.get(hooks.PENDING_REACTION_PLAYED_KEY) is True
    p1.assert_exhausted()


def test_apply_chosen_option_marks_reaction_play_even_when_canceled():
    """[LSJ 20070330]: canceled-as-played still counts as played -- the
    flag must be set even though `apply` itself is suppressed."""
    ran_effect = []

    def provider(state, context):
        del state, context
        return [
            hooks.HookOption(
                choice=Choice("tick", "Tick"),
                apply=lambda s: ran_effect.append(True),
                played_card_type="Reaction",
            )
        ]

    def cancel_provider(state, context):
        del state, context
        return [
            hooks.HookOption(choice=Choice("cancel_it", "Cancel as played"), apply=lambda s: None)
        ]

    hooks.register("fake_cancelable_reaction", provider)
    hooks.register(hooks.CANCEL_AS_PLAYED_HOOK, cancel_provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    p1 = ScriptedAgent("P1")
    p1.expect("fake_cancelable_reaction", "tick")
    p1.expect("fake_cancelable_reaction", "pass")
    p2 = ScriptedAgent("P2")
    p2.expect(hooks.CANCEL_AS_PLAYED_HOOK, "cancel_it")
    game.state.agents["P1"] = p1
    game.state.agents["P2"] = p2

    pending: dict = {}
    hooks.offer_until_pass(
        game.state, "fake_cancelable_reaction", "P1", context={"pending": pending}
    )

    assert ran_effect == []  # the effect itself was suppressed
    assert pending.get(hooks.PENDING_REACTION_PLAYED_KEY) is True  # still "played"
    p1.assert_exhausted()
    p2.assert_exhausted()


def test_apply_chosen_option_does_not_mark_pending_for_a_non_reaction_option():
    def provider(state, context):
        del state, context
        return [hooks.HookOption(choice=Choice("tick", "Tick"), apply=lambda s: None)]

    hooks.register("fake_non_reaction", provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    p1 = ScriptedAgent("P1")
    p1.expect("fake_non_reaction", "tick")
    p1.expect("fake_non_reaction", "pass")
    game.state.agents["P1"] = p1
    game.state.agents["P2"] = ScriptedAgent("P2")

    pending: dict = {}
    hooks.offer_until_pass(game.state, "fake_non_reaction", "P1", context={"pending": pending})

    assert hooks.PENDING_REACTION_PLAYED_KEY not in pending
    p1.assert_exhausted()


def test_apply_chosen_option_is_a_no_op_when_no_pending_dict_is_tracked():
    """`context` carrying no `"pending"` key at all (true of most hook call
    sites outside an action's own stealth/intercept ping-pong) must not
    raise."""

    def provider(state, context):
        del state, context
        return [
            hooks.HookOption(
                choice=Choice("tick", "Tick"), apply=lambda s: None, played_card_type="Reaction"
            )
        ]

    hooks.register("fake_reaction_no_pending", provider)
    builder = ScenarioBuilder(seed=1)
    game = builder.player("P1", pool=30).player("P2", pool=30).build()
    p1 = ScriptedAgent("P1")
    p1.expect("fake_reaction_no_pending", "tick")
    p1.expect("fake_reaction_no_pending", "pass")
    game.state.agents["P1"] = p1
    game.state.agents["P2"] = ScriptedAgent("P2")

    hooks.offer_until_pass(game.state, "fake_reaction_no_pending", "P1", context={})  # no raise

    p1.assert_exhausted()


# --- The two bypassing call sites in engine/action.py -----------------------


def test_ask_modifier_bypass_site_marks_reaction_play_in_pending():
    """`_ask_modifier` (the `INTERCEPT_MODIFIER_HOOK` reactive path) calls
    `option.apply` directly, bypassing `apply_chosen_option` -- it must
    still record a Reaction-type option into `pending`."""

    def intercept_provider(state, context):
        if context.get("player") != "P2":
            return []
        return [
            hooks.HookOption(
                choice=Choice("use_reaction", "+2 intercept"),
                apply=lambda s: 2,
                played_card_type="Reaction",
            )
        ]

    hooks.register("intercept_modifier", intercept_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("intercept_modifier", "use_reaction")
    game.state.agents["P2"] = defender

    pending: dict = {}
    blocker = attempt_block(game.state, "P1", "P2", base_stealth=1, pending=pending)

    assert blocker is not None  # intercept 2 >= stealth 1
    assert pending.get(hooks.PENDING_REACTION_PLAYED_KEY) is True
    defender.assert_exhausted()


def test_ask_stealth_or_modifier_bypass_site_marks_reaction_play_in_pending():
    """`_ask_stealth_or_modifier` (the merged `STEALTH_MODIFIER_HOOK`/
    `INTERCEPT_DECREASE_HOOK`/`STEALTH_INCREASE_HOOK` reactive path) also
    calls `option.apply` directly, outside `_duel_stealth_intercept`."""

    def stealth_provider(state, context):
        if context.get("player") != "P1":
            return []
        return [
            hooks.HookOption(
                choice=Choice("use_reaction", "+1 stealth"),
                apply=lambda s: 1,
                played_card_type="Reaction",
            )
        ]

    hooks.register("stealth_modifier", stealth_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1").expect("stealth_modifier", "use_reaction")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")  # no intercept provider to try again with
    game.state.agents["P2"] = defender

    pending: dict = {}
    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0, pending=pending)

    assert blocker is None
    assert pending.get(hooks.PENDING_REACTION_PLAYED_KEY) is True
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_block_candidate_injection_branch_marks_reaction_play_in_pending():
    """`attempt_block`'s own `BLOCK_CANDIDATE_INJECTION_HOOK` branch also
    calls `option.apply` directly, never through `apply_chosen_option`."""

    def injection_provider(state, context):
        del state, context

        def apply(s):
            del s
            return None

        return [
            hooks.HookOption(
                choice=Choice("inject", "Injected block"),
                apply=apply,
                played_card_type="Reaction",
                block_candidate_instance_id="fake-instance",
            )
        ]

    hooks.register(BLOCK_CANDIDATE_INJECTION_HOOK, injection_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    defender = ScriptedAgent("P2").expect("block_attempt", "inject")
    game.state.agents["P2"] = defender

    pending: dict = {}
    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0, pending=pending)

    assert blocker is None  # the fake `apply` returns None for this mechanism test
    assert pending.get(hooks.PENDING_REACTION_PLAYED_KEY) is True
    defender.assert_exhausted()


# --- ACTION_SUCCEEDED_HOOK forwarding `pending` ------------------------------


def test_action_succeeded_hook_receives_pending_with_reaction_flag_set():
    """End-to-end through `perform_minion_action`: a Reaction card played
    during the block-attempt ping-pong must still be visible to
    `ACTION_SUCCEEDED_HOOK`'s own provider via the forwarded `pending`."""

    def stealth_provider(state, context):
        if context.get("player") != "P1":
            return []
        return [
            hooks.HookOption(
                choice=Choice("use_reaction", "+5 stealth"),
                apply=lambda s: 5,
                played_card_type="Reaction",
            )
        ]

    captured_pending: list[dict] = []

    def succeeded_provider(state, context):
        del state
        captured_pending.append(context["pending"])

    hooks.register("stealth_modifier", stealth_provider)
    hooks.register(ACTION_SUCCEEDED_HOOK, succeeded_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    acting = game.vampire("V1")
    actor = ScriptedAgent("P1")
    actor.expect("stealth_modifier", "use_reaction")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")  # intercept 0 never catches stealth 5
    game.state.agents["P2"] = defender
    resolved: list[bool] = []

    def resolve(pending):
        del pending
        resolved.append(True)

    perform_minion_action(game.state, "P1", "P2", acting, base_stealth=0, resolve=resolve)

    assert resolved == [True]
    assert len(captured_pending) == 1
    assert captured_pending[0].get(hooks.PENDING_REACTION_PLAYED_KEY) is True
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_action_succeeded_hook_pending_has_no_reaction_flag_when_none_played():
    """Zero-regression check: with no Reaction card played during the
    action, the forwarded `pending` carries no (or a falsy) flag."""
    captured_pending: list[dict] = []

    def succeeded_provider(state, context):
        del state
        captured_pending.append(context["pending"])

    hooks.register(ACTION_SUCCEEDED_HOOK, succeeded_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)  # no ready vampire: unblockable
    game = builder.build()
    acting = game.vampire("V1")
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")

    def resolve(pending):
        del pending

    perform_minion_action(game.state, "P1", "P2", acting, base_stealth=0, resolve=resolve)

    assert len(captured_pending) == 1
    assert captured_pending[0].get(hooks.PENDING_REACTION_PLAYED_KEY, False) is False


# --- The fifth bypassing call site: politics.py::_cast_votes's own cancel --


def test_cast_votes_cancel_branch_marks_reaction_play_in_pending():
    """`_cast_votes`'s mid-cast cancel-choice branch
    (`cancel_by_value[answer].apply(state)`) also calls `option.apply`
    directly, never through `apply_chosen_option` -- it must still record a
    Reaction-type option into `resolve_referendum`'s own local `pending`
    (rules-auditor finding: this was the fifth, previously-uninstrumented
    call site)."""

    used: list[bool] = []

    def cancel_provider(state, context):
        del state
        if context.get("phase") != "mid_cast" or used:
            return []

        def apply(s):
            del s
            used.append(True)
            return "nonexistent_source"

        return [
            hooks.HookOption(
                choice=Choice("cancel_vote", "Cancel a vote"),
                apply=apply,
                played_card_type="Reaction",
            )
        ]

    hooks.register(POLLING_STEP_HOOK, cancel_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    acting = game.vampire("V1")
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("polling_step_cast", "cancel_vote")
    game.state.agents["P2"] = defender

    pending: dict = {}
    resolve_referendum(game.state, "P1", "P2", acting, action_pending=pending)

    assert pending.get(hooks.PENDING_REACTION_PLAYED_KEY) is True
    actor.assert_exhausted()
    defender.assert_exhausted()


# --- resolve_referendum bridges its own local `pending` into action_pending -


def test_resolve_referendum_bridges_reaction_played_flag_through_perform_minion_action():
    """`resolve_referendum` allocates its own local `pending` dict for
    polling/tally, separate from the action's own -- a Reaction/Action-
    Modifier card played during polling (e.g. `cards/scalpel_tongue.py`'s
    non-caller use, modeled here with a trivial fake mid-cast cancel
    provider) must still be visible via the `action_pending` passed in,
    exactly like `PENDING_REFERENDUM_RESULT_KEY` already is, and from there
    to `ACTION_SUCCEEDED_HOOK`'s own forwarded `pending` (rules-auditor
    finding)."""
    used: list[bool] = []

    def cancel_provider(state, context):
        del state
        if context.get("phase") != "mid_cast" or used:
            return []

        def apply(s):
            del s
            used.append(True)
            return "nonexistent_source"

        return [
            hooks.HookOption(
                choice=Choice("cancel_vote", "Cancel a vote"),
                apply=apply,
                played_card_type="Reaction",
            )
        ]

    captured_pending: list[dict] = []

    def succeeded_provider(state, context):
        del state
        captured_pending.append(context["pending"])

    hooks.register(POLLING_STEP_HOOK, cancel_provider)
    hooks.register(ACTION_SUCCEEDED_HOOK, succeeded_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)  # no ready vampire: political action unblockable
    game = builder.build()
    acting = game.vampire("V1")

    def resolve(pending):
        resolve_referendum(game.state, "P1", "P2", acting, action_pending=pending)

    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("polling_step_cast", "cancel_vote")
    game.state.agents["P2"] = defender

    perform_minion_action(
        game.state,
        "P1",
        "P2",
        acting,
        base_stealth=POLITICAL_ACTION_STEALTH,
        resolve=resolve,
        action=ACTION_POLITICAL,
    )

    assert len(captured_pending) == 1
    assert captured_pending[0].get(hooks.PENDING_REACTION_PLAYED_KEY) is True
    actor.assert_exhausted()
    defender.assert_exhausted()
