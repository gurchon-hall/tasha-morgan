"""The per-minion-action `pending` scratch container (OQ-11,
`docs/OPEN_QUESTIONS.md`): `engine/action.py::perform_minion_action`
constructs one shared, mutable `pending: dict[str, Any]` *before*
`attempt_block` runs, threads it into the `"stealth_modifier"`/
`"intercept_modifier"` hook context of the block-attempt phase, and passes
the same object into `resolve` once the action goes unblocked -- so a
single card play offered during the earlier phase can stash something for
its own later provider call (e.g. `_perform_bleed`'s
`"bleed_amount_modifier"` window, `engine/phases/minion.py`) to read back
and fold into that window's own clamped computation, rather than applying
it immediately and desynchronizing from that computation's floor-at-0 clamp
and Edge-holder check (OQ-11's rejected "immediate separate pool loss"
alternative, which overcharges the defender in exactly the worked example
`test_pending_bleed_bonus_and_a_later_amount_window_reduction_share_one_clamp`
below reproduces).

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using trivial fake providers -- Bonding itself remains
`card-implementer`'s job once it is wired against this capability.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import ACTION_BLEED, attempt_block, perform_minion_action
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.minion import PENDING_BLEED_AMOUNT_KEY, minion_phase


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def test_attempt_block_defaults_to_a_fresh_pending_dict_when_none_supplied():
    """Zero-regression check: callers that do not pass `pending` (e.g. every
    existing `tests/rules/test_block_attempts.py` call, or `political_action`
    which has no later window to feed) still work, and the hook context
    carries an empty dict rather than `None` or a missing key."""
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
    assert seen_context["pending"] == {}


def test_perform_minion_action_threads_one_shared_pending_dict_into_attempt_block_and_resolve():
    """The lower-level proof: a `"stealth_modifier"` provider's `apply()`
    (invoked during the block-attempt phase) mutates `context["pending"]`,
    and `perform_minion_action`'s own `resolve` callback -- invoked only
    later, once the action goes unblocked -- receives that *same* mutated
    object, not a copy or a fresh one."""

    def stealth_and_stash_provider(state, context):
        if context.get("action") != "probe":
            return []

        def _apply(s):
            context["pending"]["stashed"] = 1
            return 1  # +1 stealth: makes this attempt fail to connect.

        return [hooks.HookOption(choice=Choice("bump", "+1 stealth, stash"), apply=_apply)]

    hooks.register("stealth_modifier", stealth_and_stash_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1").expect("stealth_modifier", "bump")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")  # stealth(1) > intercept(0) now
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    captured = {}

    def resolve(pending):
        captured["pending"] = pending

    perform_minion_action(
        game.state, "P1", "P2", game.vampire("V1"), base_stealth=0, resolve=resolve, action="probe"
    )

    assert captured["pending"] == {"stashed": 1}
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_resolve_receives_an_empty_pending_dict_when_no_providers_are_registered():
    """Zero-regression / scaffolding check: with nothing registered against
    any hook, `_perform_bleed`'s `resolve` still receives a `pending` dict
    (empty), and folds in nothing -- byte-for-byte the pre-OQ-11 result."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)  # no ready vampire: no block_attempt decision at all
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # base bleed 1 only
    assert game.state.edge_holder == "P1"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_pending_bleed_amount_bonus_is_folded_into_the_bleed_before_the_amount_window():
    """End-to-end via the real `_perform_bleed`/`minion_phase` call site: a
    fake stand-in for a card whose single play ("[DOM] +1 stealth and +1
    bleed") must deliver both effects from one `"stealth_modifier"` option,
    gated on `action == ACTION_BLEED` (OQ-9) and stashing its bleed
    contribution under `PENDING_BLEED_AMOUNT_KEY` (OQ-11) for
    `_perform_bleed`'s `resolve` to fold in."""

    def stealth_and_stash_provider(state, context):
        if context.get("action") != ACTION_BLEED:
            return []

        def _apply(s):
            pending = context["pending"]
            pending[PENDING_BLEED_AMOUNT_KEY] = pending.get(PENDING_BLEED_AMOUNT_KEY, 0) + 1
            return 1  # +1 stealth, delivered from the very same play

        return [hooks.HookOption(choice=Choice("bump", "+1 stealth, +1 bleed"), apply=_apply)]

    hooks.register("stealth_modifier", stealth_and_stash_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("stealth_modifier", "bump")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")  # stealth(1) > intercept(0) now
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # base bleed 1 + stashed 1 = 2
    assert game.state.edge_holder == "P1"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_pending_bleed_bonus_and_a_later_amount_window_reduction_share_one_clamp():
    """Reproduces OQ-11's own worked example: a stashed +1 (from the earlier
    stealth window) and a later -2 reduction (offered in the
    `"bleed_amount_modifier"` window) must fold into *one* clamped
    computation -- `max(0, 1 + 1 - 2) == 0` lost, no Edge transfer -- not two
    separately-clamped pool losses (which would overcharge the defender by 1,
    the exact failure mode OQ-11's rejected "apply immediately" alternative
    produced). Also confirms `pending` is threaded into the
    `"bleed_amount_modifier"` hook's own context, not just the earlier
    stealth window's."""
    seen_pending_in_amount_window = []

    def stealth_and_stash_provider(state, context):
        if context.get("action") != ACTION_BLEED:
            return []

        def _apply(s):
            pending = context["pending"]
            pending[PENDING_BLEED_AMOUNT_KEY] = pending.get(PENDING_BLEED_AMOUNT_KEY, 0) + 1
            return 1

        return [hooks.HookOption(choice=Choice("bump", "+1 stealth, +1 bleed"), apply=_apply)]

    def reduce_by_two(state, context):
        if context.get("player") != "P2":
            return []
        seen_pending_in_amount_window.append(dict(context.get("pending", {})))
        amount_box = context["amount"]
        if amount_box[0] <= 0:
            return []

        def _apply(s):
            amount_box[0] -= 2

        return [hooks.HookOption(choice=Choice("reduce", "-2 bleed"), apply=_apply)]

    hooks.register("stealth_modifier", stealth_and_stash_provider)
    hooks.register("bleed_amount_modifier", reduce_by_two)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("stealth_modifier", "bump")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")
    defender.expect("bleed_amount_modifier", "reduce")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # max(0, 1 + 1 - 2) == 0 lost, not 1 (overcharge)
    assert game.state.edge_holder is None
    assert seen_pending_in_amount_window[0] == {PENDING_BLEED_AMOUNT_KEY: 1}
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_hunt_resolve_accepts_but_ignores_the_pending_argument():
    """`_perform_hunt`'s `resolve` closure gained the same `pending`
    argument (the shared call-site signature `perform_minion_action`
    requires) but has no later hook window to feed -- a stash during hunt's
    own stealth/intercept ping-pong must have zero effect on hunt's own
    blood-gain effect, and must not raise."""
    used = [False]

    def intercept_and_stash_provider(state, context):
        if context.get("action") != "hunt" or used[0]:
            return []

        def _apply(s):
            context["pending"]["unused"] = 99
            used[0] = True
            return 0  # no real intercept change: this attempt still fails to connect

        return [hooks.HookOption(choice=Choice("stash", "stash only"), apply=_apply)]

    hooks.register("intercept_modifier", intercept_and_stash_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")  # mandatory hunt: no bleed/hunt choice offered
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("intercept_modifier", "stash")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.blood_of("V1") == 1  # hunt succeeded, unaffected by the stash
    actor.assert_exhausted()
    defender.assert_exhausted()
