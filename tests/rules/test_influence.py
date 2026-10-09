"""Influence phase: 2P transfer ramp and all four transfer/action types.

Source: Rulebook SS4 Influence Phase, replaced by 2P variant SS2.3 (per the
`vtes-rules-reference` skill condensed mapping): "4 transfers. ... first
player gets 3 on their first influence phase, then 4 for all. Costs: 1
transfer = 1 pool -> uncontrolled vampire; 2 transfers = 1 blood from
uncontrolled vampire -> pool; 4 transfers + burn 1 pool = move a crypt card
to the uncontrolled region. A vampire with blood >= capacity may be revealed
into the ready region, unlocked, any time in this phase."
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine.phases.influence import influence_phase


def test_first_influence_phase_of_the_game_grants_three_transfers():
    """2P variant SS2.3: the very first influence phase of the game gets 3
    transfers (not 4); spending all of it on 1-transfer add-blood actions
    proves the count."""
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=False)
    builder.player("P1", pool=30).uncontrolled_vampire("V1", capacity=5, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("influence_action", "add_blood:V1")
    agent.expect("influence_action", "add_blood:V1")
    agent.expect("influence_action", "add_blood:V1")
    # 3 transfers now spent (of the first-phase budget of 3): nothing legal
    # remains (blood 3 < capacity 5, so no reveal either), so the phase ends
    # on its own without a 4th decision ("only when needed").
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert game.blood_of("V1") == 3  # 3 transfers spent, not 4
    assert game.pool_of("P1") == 27
    agent.assert_exhausted()


def test_later_influence_phases_grant_four_transfers():
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    builder.player("P1", pool=30).uncontrolled_vampire("V1", capacity=5, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    for _ in range(4):
        agent.expect("influence_action", "add_blood:V1")
    # All 4 transfers spent; blood (4) < capacity (5): nothing legal remains.
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert game.blood_of("V1") == 4
    agent.assert_exhausted()


def test_add_blood_not_offered_once_vampire_is_at_capacity():
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    builder.player("P1", pool=30).uncontrolled_vampire("V1", capacity=2, blood=2)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1").expect("influence_action", "reveal:V1")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert game.zone_of("V1") == "ready"


def test_remove_blood_transfer_refunds_pool_at_two_transfers():
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    builder.player("P1", pool=10).uncontrolled_vampire("V1", capacity=5, blood=2)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("influence_action", "remove_blood:V1")
    agent.expect("influence_action", "end_phase")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert game.blood_of("V1") == 1
    assert game.pool_of("P1") == 11
    agent.assert_exhausted()


def test_bring_crypt_card_costs_four_transfers_and_one_pool():
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    p1 = builder.player("P1", pool=10)
    p1.crypt_deck_cards(count=1, name_prefix="fresh")
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1").expect("influence_action", "bring_crypt")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert game.pool_of("P1") == 9
    uncontrolled_names = [
        v.card.name for v in game.state.players["P1"].vampires.values() if v.zone == "uncontrolled"
    ]
    assert "fresh-0" in uncontrolled_names
    assert len(game.state.players["P1"].crypt_deck) == 0
    agent.assert_exhausted()


def test_bring_crypt_not_offered_with_fewer_than_four_transfers_remaining():
    """1st influence phase of the game only grants 3 transfers, never enough
    for the 4-transfer bring-crypt action."""
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=False)
    p1 = builder.player("P1", pool=10)
    p1.crypt_deck_cards(count=1)
    builder.player("P2", pool=30)
    game = builder.build()
    # No uncontrolled vampires exist and the crypt deck can't be reached at 3
    # transfers: nothing legal at all, so no decision is raised whatsoever.
    agent = ScriptedAgent("P1")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")  # must not raise

    assert len(game.state.players["P1"].crypt_deck) == 1  # untouched
    agent.assert_exhausted()


def test_reveal_is_free_and_available_any_time_in_the_phase():
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    builder.player("P1", pool=30).uncontrolled_vampire("V1", capacity=3, blood=3)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("influence_action", "reveal:V1")
    # After revealing, V1 is no longer uncontrolled: nothing legal remains.
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert game.zone_of("V1") == "ready"
    assert game.vampire("V1").locked is False
    agent.assert_exhausted()


def test_can_end_the_phase_early_while_legal_actions_remain():
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    builder.player("P1", pool=30).uncontrolled_vampire("V1", capacity=5, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("influence_action", "add_blood:V1")
    agent.expect("influence_action", "end_phase")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert game.blood_of("V1") == 1  # stopped early, 3 transfers unused
    assert game.pool_of("P1") == 29
    agent.assert_exhausted()


def test_revealing_a_duplicate_name_flags_a_2p_contest():
    """2P variant: contested crypt cards stay in play and usable; this test
    exercises the (OQ-4) reveal-triggers-the-contest reading."""
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    builder.player("P1", pool=30).uncontrolled_vampire(
        "V1", capacity=1, blood=1, name="Shared Name"
    )
    builder.player("P2", pool=30).ready_vampire("W1", capacity=1, blood=1, name="Shared Name")
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("influence_action", "reveal:V1")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert game.vampire("V1").contested_with == "W1"
    assert game.vampire("W1").contested_with == "V1"
    agent.assert_exhausted()
