"""`REFERENDUM_RESOLVED_HOOK` dispatch (OQ-36, `docs/OPEN_QUESTIONS.md`):
`engine/action.py::perform_minion_action` fires it only once a political
action's own `resolve()` closure (which itself calls `engine/politics.py::
resolve_referendum`, passing it `action_pending=pending`, and then runs its
own pass effects) fully returns, and only when the referendum passed --
Voter Captivation's own trigger moment.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a trivial fake `"action_card_play"` provider mirroring
`cards/kine_resources_contested.py`'s own real shape -- Voter Captivation's
own card module remains `card-implementer`'s job once this capability
exists.
"""

from typing import Any

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import ACTION_POLITICAL, REFERENDUM_RESOLVED_HOOK
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, ActionCardSpec, minion_phase
from vtesbot.engine.politics import POLITICAL_ACTION_STEALTH, resolve_referendum

FAKE_PA_KRCG_ID = 701


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def _fake_political_action_provider(state, context):
    """Stand-in for a real Political Action card module's own
    `"action_card_play"` provider, mirroring `cards/kine_resources_
    contested.py`'s exact shape: `resolve()` calls `resolve_referendum`
    with `action_pending=pending` and has no further pass effect of its
    own (the referendum passing or failing is this fake card's entire
    text)."""
    player = context["player"]
    acting_vampire_id = context["vampire"]
    acting_vampire = state.players[player].vampires.get(acting_vampire_id)
    if acting_vampire is None or not any(
        c.krcg_id == FAKE_PA_KRCG_ID for c in state.players[player].hand
    ):
        return []
    other = state.other_player(player)

    def _apply(s):
        s.players[player].hand = [c for c in s.players[player].hand if c.krcg_id != FAKE_PA_KRCG_ID]

        def resolve(pending: dict[str, Any]) -> None:
            resolve_referendum(s, player, other, acting_vampire, action_pending=pending)

        return ActionCardSpec(
            base_stealth=POLITICAL_ACTION_STEALTH,
            directed=False,
            action=ACTION_POLITICAL,
            resolve=resolve,
        )

    return [
        HookOption(
            choice=Choice("play_fake_pa", "Play Fake Political Action"),
            apply=_apply,
        )
    ]


def _build_passing_scenario():
    """No candidate blocker, no titled vampires, no Edge holder: the only
    vote source is the acting Methuselah's own political-action-card vote,
    cast "for" -- 1-0, passes (mirrors `tests/rules/test_politics.py::
    test_an_uncontested_referendum_passes_one_to_nothing`)."""
    hooks.register(ACTION_CARD_PLAY_HOOK, _fake_political_action_provider)
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    pb.hand.append(LibraryCard(krcg_id=FAKE_PA_KRCG_ID, name="Fake PA", card_type="action"))
    builder.player("P2", pool=30)
    return builder.build()


def test_referendum_resolved_hook_fires_after_a_passing_referendum_with_the_vote_margin():
    """`resolve_impulse_window` offers the hook to each side in turn
    (`engine/hooks.py`'s own alternation), so a provider that does not
    itself filter on `context["player"]` may be *called* more than once --
    mirrors `tests/rules/test_politics.py::
    test_the_pre_cast_and_post_tally_hook_contexts_both_carry_the_calling_
    vampires_identity`'s own precedent for `POLLING_STEP_HOOK`. What matters
    is that it fires at least once, and every call sees the correct
    context."""
    seen: list[dict] = []

    def recorder(state, context):
        del state
        seen.append(dict(context))
        return []

    hooks.register(REFERENDUM_RESOLVED_HOOK, recorder)
    game = _build_passing_scenario()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "play_fake_pa")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen
    for context in seen:
        assert context["caller"] == "P1"
        assert context["other"] == "P2"
        assert context["caller_vampire_id"] == "V1"
        assert context["margin"] == 1  # 1 for, 0 against
    actor.assert_exhausted()


def test_referendum_resolved_hook_does_not_fire_when_the_referendum_fails():
    seen: list[dict] = []

    def recorder(state, context):
        del state
        seen.append(dict(context))
        return []

    hooks.register(REFERENDUM_RESOLVED_HOOK, recorder)
    game = _build_passing_scenario()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "play_fake_pa")
    actor.expect("polling_step_cast", "pass")  # declines its own vote: 0-0 ties, fails
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen == []
    actor.assert_exhausted()


def test_referendum_resolved_hook_does_not_fire_when_the_action_is_blocked():
    """A blocked political action never calls a referendum at all (OQ-5):
    nothing is ever written to `pending[PENDING_REFERENDUM_RESULT_KEY]`.

    Political action's own +1 baseline stealth always evades a bare block
    attempt (mirrors `tests/rules/test_politics.py::
    test_a_blocked_political_action_goes_to_combat_and_never_calls_a_
    referendum`'s own reasoning), so a fake intercept booster stands in for
    a real intercept-granting card purely to exercise the "blocked ->
    combat" path end to end."""

    def fake_intercept(state, context):
        if context.get("player") != "P2":
            return []
        return [HookOption(choice=Choice("use_fake_intercept", "+2 intercept"), apply=lambda s: 2)]

    seen: list[dict] = []

    def recorder(state, context):
        del state
        seen.append(dict(context))
        return []

    hooks.register(REFERENDUM_RESOLVED_HOOK, recorder)
    hooks.register(ACTION_CARD_PLAY_HOOK, _fake_political_action_provider)
    hooks.register("intercept_modifier", fake_intercept)
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    pb.hand.append(LibraryCard(krcg_id=FAKE_PA_KRCG_ID, name="Fake PA", card_type="action"))
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "play_fake_pa")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("intercept_modifier", "use_fake_intercept")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert seen == []
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_referendum_resolved_hook_fires_with_no_providers_registered():
    """Zero-regression check: with nothing registered, the two-sided
    `resolve_impulse_window` closes immediately with no `Decision` raised
    (CLAUDE.md "only when needed")."""
    game = _build_passing_scenario()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "play_fake_pa")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")  # must not raise

    actor.assert_exhausted()


def test_resolve_referendum_without_action_pending_is_unaffected():
    """Zero-regression check: `political_action` (and every pre-existing
    caller) never passes `action_pending`, so this function's own new write
    is a pure no-op for it -- same tally/pass-fail result as before."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    votes_for, votes_against, _casts = resolve_referendum(
        game.state, "P1", "P2", game.vampire("V1")
    )

    assert (votes_for, votes_against) == (1, 0)
    actor.assert_exhausted()
