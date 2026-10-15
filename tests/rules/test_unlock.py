"""Unlock phase: unlocking, Edge pool gain, and 2P contested crypt cards.

Source: Rulebook §4 Unlock Phase + 2P variant (per the `vtes-rules-reference`
skill condensed mapping): "unlock all your cards, then unlock-phase effects
in the order you choose; Edge holder may gain 1 pool. Contests paid here (1
pool per contested card ...)." 2P variant: "contested crypt cards stay in
play and usable; contest costs 1 pool each unlock phase or yield (burn)."
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.unlock import UNLOCK_PHASE_MANDATORY_EFFECT_HOOK, unlock_phase


def test_unlock_phase_unlocks_ready_vampires():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1").ready_vampire("V1", capacity=3, blood=1, locked=True)
    builder.player("P2")
    game = builder.build()
    game.state.agents["P1"] = ScriptedAgent("P1")  # no pending effects: no decisions expected

    unlock_phase(game.state, "P1")

    assert game.vampire("V1").locked is False


def test_edge_holder_may_gain_pool():
    """ "Edge holder may gain 1 pool" -- optional, Rulebook §4 Unlock Phase."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10)
    builder.player("P2")
    builder.edge_holder("P1")
    game = builder.build()
    game.state.agents["P1"] = ScriptedAgent("P1").expect("edge_pool_gain", "gain_pool")

    unlock_phase(game.state, "P1")

    assert game.pool_of("P1") == 11
    game.state.agents["P1"].assert_exhausted()


def test_edge_holder_may_decline_pool_gain():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10)
    builder.player("P2")
    builder.edge_holder("P1")
    game = builder.build()
    game.state.agents["P1"] = ScriptedAgent("P1").expect("edge_pool_gain", "decline")

    unlock_phase(game.state, "P1")

    assert game.pool_of("P1") == 10


def test_non_edge_holder_is_not_offered_the_gain():
    """ "Only when needed": no edge_pool_gain decision is raised for a player who
    does not hold the Edge."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10)
    builder.player("P2")
    builder.edge_holder("P2")
    game = builder.build()
    game.state.agents["P1"] = ScriptedAgent("P1")  # no decisions expected at all

    unlock_phase(game.state, "P1")  # must not raise UnexpectedDecisionError

    assert game.pool_of("P1") == 10


def test_contest_pay_keeps_both_copies_in_play():
    """2P variant: contested crypt cards stay in play and usable; pay 1 pool to keep contesting."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10).ready_vampire("P1-V1", capacity=3, blood=1)
    builder.player("P2", pool=10).ready_vampire("P2-V1", capacity=3, blood=1)
    game = builder.build()
    game.vampire("P1-V1").contested_with = "P2-V1"
    game.vampire("P2-V1").contested_with = "P1-V1"
    game.state.agents["P1"] = ScriptedAgent("P1").expect("contest_resolution", "pay")

    unlock_phase(game.state, "P1")

    assert game.pool_of("P1") == 9
    assert game.zone_of("P1-V1") == "ready"
    assert game.vampire("P1-V1").contested_with == "P2-V1"
    # untouched; P2 resolves it on their own unlock phase
    assert game.vampire("P2-V1").contested_with == "P1-V1"


def test_contest_yield_burns_own_copy_and_clears_opponent_status():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10).ready_vampire("P1-V1", capacity=3, blood=1)
    builder.player("P2", pool=10).ready_vampire("P2-V1", capacity=3, blood=1)
    game = builder.build()
    game.vampire("P1-V1").contested_with = "P2-V1"
    game.vampire("P2-V1").contested_with = "P1-V1"
    game.state.agents["P1"] = ScriptedAgent("P1").expect("contest_resolution", "yield")

    unlock_phase(game.state, "P1")

    assert game.pool_of("P1") == 10  # yielding costs no pool
    assert game.zone_of("P1-V1") == "burned"
    assert game.vampire("P2-V1").contested_with is None


def test_multiple_pending_unlock_effects_let_the_player_choose_order():
    """Rulebook §4: "unlock-phase effects in the order you choose."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10).ready_vampire("P1-V1", capacity=3, blood=1)
    builder.player("P2", pool=10).ready_vampire("P2-V1", capacity=3, blood=1)
    builder.edge_holder("P1")
    game = builder.build()
    game.vampire("P1-V1").contested_with = "P2-V1"
    game.vampire("P2-V1").contested_with = "P1-V1"
    agent = ScriptedAgent("P1")
    agent.expect("unlock_phase_order", "edge_gain")
    agent.expect("edge_pool_gain", "gain_pool")
    agent.expect("contest_resolution", "pay")
    game.state.agents["P1"] = agent

    unlock_phase(game.state, "P1")

    assert game.pool_of("P1") == 10  # +1 from edge, -1 from contest
    agent.assert_exhausted()


# --- `rules-auditor` finding: colliding mandatory-effect choice values -----


def test_colliding_mandatory_effect_choice_values_raise_instead_of_dropping_one():
    """MAJOR audit finding: `_mandatory_effect_options`'s dict comprehension
    keys each `HookOption` by `f"mandatory:{option.choice.value}"` with no
    collision guard -- two providers offering the same raw `Choice.value`
    would silently collapse to one dict entry, permanently discarding the
    first provider's `HookOption` (including its own `apply`) with no error,
    no log, no `Decision` (mirrors `test_influence.py`'s own OQ-24 addendum
    repro for the influence-phase equivalent). Repro: two toy providers both
    choosing `Choice("burn_1_pool", ...)`. Before the fix: the second
    provider's option would silently win the dict and the first's `apply`
    would never run. After the fix: `unlock_phase` raises `ValueError`
    before ever building the `unlock_phase_order` `Decision`."""

    def _provider_a(state, context):
        return [
            hooks.HookOption(
                choice=Choice("burn_1_pool", "Provider A burns 1 pool"),
                apply=lambda s: None,
            )
        ]

    def _provider_b(state, context):
        return [
            hooks.HookOption(
                choice=Choice("burn_1_pool", "Provider B burns 1 pool"),
                apply=lambda s: None,
            )
        ]

    hooks.register(UNLOCK_PHASE_MANDATORY_EFFECT_HOOK, _provider_a)
    hooks.register(UNLOCK_PHASE_MANDATORY_EFFECT_HOOK, _provider_b)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10)
    builder.player("P2", pool=10)
    game = builder.build()
    game.state.agents["P1"] = ScriptedAgent("P1")  # never reached: raises first

    with pytest.raises(ValueError, match="duplicate choice value"):
        unlock_phase(game.state, "P1")
