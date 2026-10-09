"""Default bleed action + block attempts (Rulebook SS4 Minion Phase; 2P Edge mechanic).

"Default actions: bleed (directed, 0 stealth, bleed 1, one bleed per minion
per turn, successful bleed >=1 takes the Edge ...)." "Block attempts:
directed action -> only the targeted Methuselah may block. ... Declining to
block is final unless the target changes."
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine.phases.minion import minion_phase


def test_unblocked_bleed_reduces_prey_pool_and_takes_the_edge():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("minion_phase_choice", "act_with:V1")
    agent.expect("action_choice", "bleed")
    # V1 is now locked and is P1's only vampire: no candidates remain, so the
    # phase ends on its own without an "end_minion_phase" decision.
    game.state.agents["P1"] = agent
    game.state.agents["P2"] = ScriptedAgent("P2")  # no ready vampire: no block decision raised

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29
    assert game.state.edge_holder == "P1"
    agent.assert_exhausted()


def test_defender_may_decline_to_block():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    defender = ScriptedAgent("P2").expect("block_attempt", "decline")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29
    assert game.state.edge_holder == "P1"
    assert game.vampire("B1").locked is False  # declining does not lock the blocker
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_successful_block_locks_blocker_and_prevents_bleed_from_resolving():
    """Bleed has 0 baseline stealth, so a blocker's 0 baseline intercept always
    succeeds when attempted (intercept >= stealth, 0 >= 0)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    # Combat round: both strike (hand_strike default), then neither presses.
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # bleed did not resolve
    assert game.state.edge_holder is None
    assert game.vampire("B1").locked is True  # a successful block locks the blocker
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_bleed_with_no_candidate_blocker_skips_the_block_decision():
    """ "Only when needed": with no ready unlocked vampire to block with, no
    block_attempt decision is raised at all."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).torpid_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29
    actor.assert_exhausted()


def test_can_end_minion_phase_early_with_a_ready_vampire_remaining():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=3, blood=1)
    p1.ready_vampire("V2", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1").expect("minion_phase_choice", "end_minion_phase")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # nothing happened
    actor.assert_exhausted()


def test_bleed_ousts_prey_at_zero_pool_and_ends_the_game():
    """Rulebook SS5: pool 0 -> ousted; the sole predator gets 1 VP + 6 pool,
    and (2P structural consequence) +1 more VP as the last Methuselah."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 0
    assert "P2" in game.state.eliminated
    assert game.state.game_over is True
    assert game.state.winner == "P1"
    assert game.state.victory_points["P1"] == 2
    assert game.pool_of("P1") == 30 + 6
