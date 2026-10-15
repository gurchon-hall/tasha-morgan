"""Influence phase: 2P transfer ramp and all four transfer/action types.

Source: Rulebook §4 Influence Phase, replaced by 2P variant §2.3 (per the
`vtes-rules-reference` skill condensed mapping): "4 transfers. ... first
player gets 3 on their first influence phase, then 4 for all. Costs: 1
transfer = 1 pool -> uncontrolled vampire; 2 transfers = 1 blood from
uncontrolled vampire -> pool; 4 transfers + burn 1 pool = move a crypt card
to the uncontrolled region. A vampire with blood >= capacity may be revealed
into the ready region, unlocked, any time in this phase."

The `test_*influence_phase_action_hook*` tests below prove OQ-24's own new
`INFLUENCE_PHASE_ACTION_HOOK` (`docs/OPEN_QUESTIONS.md`), added to unblock
Wider View (krcg id 102180): fake providers standing in for its own two
transfer-costed clauses ("You can use 1 transfer to draw 1 card from your
crypt and then remove a crypt card in your uncontrolled region from the
game. You can use 4 transfers to burn this card and gain 2 pool."),
exercised through the real, production `influence_phase` call site (not
just a lower-level helper -- same bar OQ-7/OQ-13/OQ-23's own resolutions
set), per the `rules-scenario-test` skill. Per the `implement-card`
skill/CLAUDE.md §6, Wider View itself is not implemented here -- these are
engine-mechanism scenario tests using trivial fake providers, not the real
card.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import build_observation, hooks
from vtesbot.engine.damage import remove_vampire_from_game
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.influence import INFLUENCE_PHASE_ACTION_HOOK, influence_phase
from vtesbot.engine.pool import gain_pool


def test_first_influence_phase_of_the_game_grants_three_transfers():
    """2P variant §2.3: the very first influence phase of the game gets 3
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


# --- OQ-24: INFLUENCE_PHASE_ACTION_HOOK (Wider View's own fake stand-ins) ----


def _wider_view_draw_and_remove_provider(state, context):
    """Stand-in for Wider View's "1 transfer: draw 1 card from your crypt
    and then remove a crypt card in your uncontrolled region from the game"
    clause. Mirrors the real card's own legality: offered only when the
    acting player has at least 1 transfer remaining, a non-empty
    `crypt_deck` to draw from, and at least one of their own uncontrolled
    vampires to remove (`GameState.ask`'s "legality by construction"
    invariant -- the provider's own job, per `engine/state.py`'s module
    docstring)."""
    player = context["player"]
    if context["transfers_remaining"] < 1:
        return []
    p = state.players[player]
    uncontrolled = [v for v in p.vampires.values() if v.zone == "uncontrolled"]
    if not p.crypt_deck or not uncontrolled:
        return []

    def _apply(s):
        drawn = s.players[player].crypt_deck.pop(0)
        s.players[player].hand.append(drawn)  # stand-in for "draw 1 card"
        remove_vampire_from_game(s, player, uncontrolled[0])
        return 1

    return [
        hooks.HookOption(
            choice=Choice("wider_view_draw_and_remove", "Wider View: draw and remove (1 transfer)"),
            apply=_apply,
        )
    ]


def _wider_view_burn_for_pool_provider(state, context):
    """Stand-in for Wider View's "4 transfers: burn this card and gain 2
    pool" clause."""
    player = context["player"]
    if context["transfers_remaining"] < 4:
        return []

    def _apply(s):
        gain_pool(s, player, 2)
        return 4

    return [
        hooks.HookOption(
            choice=Choice("wider_view_burn_for_pool", "Wider View: burn for 2 pool (4 transfers)"),
            apply=_apply,
        )
    ]


def test_influence_phase_action_hook_offers_a_one_transfer_draw_and_remove_option():
    hooks.register(INFLUENCE_PHASE_ACTION_HOOK, _wider_view_draw_and_remove_provider)
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    p1 = builder.player("P1", pool=30)
    p1.uncontrolled_vampire("V1", capacity=5, blood=0)
    p1.crypt_deck_cards(count=1, name_prefix="fresh")
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("influence_action", "wider_view_draw_and_remove")
    # After drawing/removing: crypt_deck is now empty and V1 is no longer
    # uncontrolled, so nothing legal remains ("only when needed" -- no
    # further decision, not even "end_phase", is raised).
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert len(game.state.players["P1"].crypt_deck) == 0
    assert any(c.name == "fresh-0" for c in game.state.players["P1"].hand)
    assert game.zone_of("V1") == "removed_from_game"
    agent.assert_exhausted()


def test_influence_phase_action_hook_is_not_offered_without_a_crypt_deck_card():
    """Legality-by-construction (`engine/state.py` module docstring): the
    provider itself must not offer the draw-and-remove option once the
    crypt deck is empty, even with an uncontrolled vampire to remove and
    transfers remaining."""
    hooks.register(INFLUENCE_PHASE_ACTION_HOOK, _wider_view_draw_and_remove_provider)
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    p1 = builder.player("P1", pool=30)
    p1.uncontrolled_vampire("V1", capacity=5, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("influence_action", "add_blood:V1")
    agent.expect("influence_action", "end_phase")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert game.zone_of("V1") == "uncontrolled"
    agent.assert_exhausted()


def test_influence_phase_action_hook_offers_a_four_transfer_burn_for_pool_option():
    hooks.register(INFLUENCE_PHASE_ACTION_HOOK, _wider_view_burn_for_pool_provider)
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1").expect("influence_action", "wider_view_burn_for_pool")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert game.pool_of("P1") == 32
    agent.assert_exhausted()


def test_four_transfer_hook_option_not_offered_with_fewer_than_four_transfers_remaining():
    """1st influence phase of the game only grants 3 transfers -- never
    enough for a 4-transfer hook option."""
    hooks.register(INFLUENCE_PHASE_ACTION_HOOK, _wider_view_burn_for_pool_provider)
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=False)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    # Nothing legal at all (no uncontrolled vampires, no crypt deck, and the
    # 4-transfer hook option needs more transfers than the 3-transfer first
    # influence phase grants): no decision raised whatsoever.
    agent = ScriptedAgent("P1")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")  # must not raise

    assert game.pool_of("P1") == 30
    agent.assert_exhausted()


def test_a_vampire_removed_from_the_game_is_fully_visible_to_both_players():
    """General ruling on file for this exact clause: "Cards removed from
    the game are public." [LSJ 20080314]. Also proves the zero-further-
    Observation-change finding: `build_observation`'s own `zone !=
    "uncontrolled"` test already covers this new zone value with no new
    branch needed."""
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    p1 = builder.player("P1", pool=30)
    p1.uncontrolled_vampire("V1", capacity=3, blood=0, name="Secret Name")
    builder.player("P2", pool=30)
    game = builder.build()

    remove_vampire_from_game(game.state, "P1", game.vampire("V1"))

    obs_opponent = build_observation(game.state, "P2")
    view = next(v for v in obs_opponent.vampires if v.instance_id == "V1")
    assert view.zone == "removed_from_game"
    assert view.name == "Secret Name"
    assert view.locked is False


def test_zero_regression_standard_transfer_types_unaffected_by_a_registered_hook_provider():
    """The three hardcoded transfer types must still be offered, and still
    cost exactly what they always have, with an unrelated hook provider
    also registered (proves the hook options are *additional* choices, not
    a replacement of the existing baseline)."""
    hooks.register(INFLUENCE_PHASE_ACTION_HOOK, _wider_view_burn_for_pool_provider)
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    builder.player("P1", pool=30).uncontrolled_vampire("V1", capacity=5, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("influence_action", "add_blood:V1")
    agent.expect("influence_action", "end_phase")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert game.blood_of("V1") == 1
    assert game.pool_of("P1") == 29
    agent.assert_exhausted()


# --- `rules-auditor` finding (OQ-24 addendum): colliding choice values ------


def test_a_colliding_hook_choice_value_raises_instead_of_silently_misrouting():
    """MAJOR audit finding: before this fix, `GameState.ask`'s own `legal =
    {c.value: c for c in decision.choices}` kept only the *last* `Choice`
    for a given `.value`, and `influence_phase`'s own `if choice in
    by_value: ... else: _apply(...)` routing meant a hook-provided choice
    whose value happened to collide with a hardcoded one (e.g.
    `"add_blood:{instance_id}"`) would silently take over that exact
    action -- the real hardcoded transfer type became unreachable for that
    value, with no error raised. Repro: a fake provider offers
    `Choice("add_blood:V1", ...)` with a no-op `apply` (returns 1 transfer
    consumed, touches no pool/blood at all). Before the fix: the fake
    option would have won the `by_value` lookup silently (pool/blood
    unchanged, no error). After the fix: `influence_phase` raises
    `ValueError` before ever building the `Decision`."""

    def _colliding_provider(state, context):
        return [
            hooks.HookOption(
                choice=Choice("add_blood:V1", "fake, collides with the real add_blood action"),
                apply=lambda s: 1,  # no-op: does not touch pool or blood
            )
        ]

    hooks.register(INFLUENCE_PHASE_ACTION_HOOK, _colliding_provider)
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    builder.player("P1", pool=30).uncontrolled_vampire("V1", capacity=5, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    game.state.agents["P1"] = ScriptedAgent("P1")  # never reached: raises first

    with pytest.raises(ValueError, match="duplicate choice value"):
        influence_phase(game.state, "P1")
