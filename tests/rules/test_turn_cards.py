"""`ACTION_SUCCEEDED_HOOK` and `TurnCardInPlay` (OQ-34, `docs/
OPEN_QUESTIONS.md`): `engine/action.py::perform_minion_action`'s generic
"this action just succeeded" dispatch, and `engine/turn_cards.py`'s
"stays in play for the rest of the turn, until burned" entity -- the two
primitives Loup (krcg id 102273) needs.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using trivial fake providers -- Loup's own card module remains
`card-implementer`'s job once this capability exists.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import ACTION_BLEED, ACTION_SUCCEEDED_HOOK
from vtesbot.engine.phases import play_turn
from vtesbot.engine.phases.minion import minion_phase
from vtesbot.engine.turn_cards import (
    active_turn_cards,
    bring_turn_card_into_play,
    burn_turn_card,
    clear_turn_cards_at_end_of_turn,
)

LOUP_KRCG_ID = 102273


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


# --- TurnCardInPlay / engine/turn_cards.py -----------------------------------


def test_bring_turn_card_into_play_creates_an_in_play_card():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()

    card = bring_turn_card_into_play(game.state, "P1", krcg_id=LOUP_KRCG_ID, name="Loup")

    assert card.controller == "P1"
    assert card.zone == "in_play"
    assert card.is_in_play is True
    assert game.state.players["P1"].turn_cards[card.instance_id] is card


def test_turn_card_instance_ids_are_in_their_own_namespace():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()

    card = bring_turn_card_into_play(game.state, "P1", krcg_id=LOUP_KRCG_ID, name="Loup")

    assert card.instance_id != "P1-V1"


def test_active_turn_cards_filters_by_krcg_id_and_zone():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    mine = bring_turn_card_into_play(game.state, "P1", krcg_id=LOUP_KRCG_ID, name="Loup")
    other_card = bring_turn_card_into_play(game.state, "P1", krcg_id=999, name="Something Else")
    burn_turn_card(other_card)

    assert active_turn_cards(game.state, "P1", LOUP_KRCG_ID) == [mine]
    assert active_turn_cards(game.state, "P1", 999) == []  # already burned
    assert active_turn_cards(game.state, "P2", LOUP_KRCG_ID) == []  # not this player's


def test_burn_turn_card_flips_zone_to_burned():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    card = bring_turn_card_into_play(game.state, "P1", krcg_id=LOUP_KRCG_ID, name="Loup")

    burn_turn_card(card)

    assert card.zone == "burned"
    assert card.is_in_play is False


def test_clear_turn_cards_at_end_of_turn_only_touches_in_play_cards_for_that_player():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    mine = bring_turn_card_into_play(game.state, "P1", krcg_id=LOUP_KRCG_ID, name="Loup")
    already_burned = bring_turn_card_into_play(game.state, "P1", krcg_id=999, name="Other")
    burn_turn_card(already_burned)
    theirs = bring_turn_card_into_play(game.state, "P2", krcg_id=LOUP_KRCG_ID, name="Loup")

    clear_turn_cards_at_end_of_turn(game.state, "P1")

    assert mine.zone == "burned"
    assert already_burned.zone == "burned"  # unaffected, already burned
    assert theirs.zone == "in_play"  # a different player's turn ending is unrelated


def test_play_turn_burns_an_in_play_turn_card_at_the_end_of_the_turn():
    """End-to-end via the real `engine/phases/turn.py::play_turn` call site:
    with no vampires/hand cards, every phase resolves with zero decisions
    (mirrors `tests/rules/test_turn_phases.py`), so the turn runs to
    completion and the card is burned right before the turn flips."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    card = bring_turn_card_into_play(game.state, "P1", krcg_id=LOUP_KRCG_ID, name="Loup")

    play_turn(game.state)

    assert card.zone == "burned"
    assert game.state.active_player == "P2"


def test_play_turn_does_not_burn_the_other_players_turn_card():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    theirs = bring_turn_card_into_play(game.state, "P2", krcg_id=LOUP_KRCG_ID, name="Loup")

    play_turn(game.state)  # P1's own turn ends; P2's card is untouched

    assert theirs.zone == "in_play"


# --- ACTION_SUCCEEDED_HOOK / engine/action.py --------------------------------


def test_action_succeeded_hook_fires_after_an_unblocked_bleed_with_the_full_context():
    seen: list[dict] = []

    def recorder(state, context):
        del state
        seen.append(dict(context))

    hooks.register(ACTION_SUCCEEDED_HOOK, recorder)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)  # no ready vampire: unblockable
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert len(seen) == 1
    assert seen[0]["actor_player"] == "P1"
    assert seen[0]["vampire"] is game.vampire("V1")
    assert seen[0]["action"] == ACTION_BLEED
    actor.assert_exhausted()


def test_action_succeeded_hook_does_not_fire_when_the_action_is_blocked():
    """Rulebook SS4 "Resolve the Action": "An action is successful only if
    it is not blocked" -- a blocked action's own effect never happens, and
    neither does this generic signal."""
    seen: list[dict] = []

    def recorder(state, context):
        del state
        seen.append(dict(context))

    hooks.register(ACTION_SUCCEEDED_HOOK, recorder)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert seen == []
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_action_succeeded_hook_fires_with_no_providers_registered():
    """Zero-regression check: `hooks.run_effects` with nothing registered is
    a safe no-op, exactly like every other such hook in this engine."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")  # must not raise

    actor.assert_exhausted()


# --- Composed Loup-shaped stand-in -------------------------------------------


def test_loup_shaped_stand_in_is_burned_after_a_toreador_performs_a_successful_action():
    """Proves the two primitives compose into Loup's own printed burn
    condition 2 ("Burn this card ... after a Toreador performs a successful
    action") without any card-specific logic inside the engine -- the fake
    provider below is exactly what a future `cards/loup.py` module would
    register against `ACTION_SUCCEEDED_HOOK` itself."""

    def loup_auto_burn(state, context):
        vampire = context["vampire"]
        if vampire.card.clan != "Toreador":
            return
        for card in active_turn_cards(state, context["actor_player"], LOUP_KRCG_ID):
            burn_turn_card(card)

    hooks.register(ACTION_SUCCEEDED_HOOK, loup_auto_burn)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Toreador")
    builder.player("P2", pool=30)
    game = builder.build()
    card = bring_turn_card_into_play(game.state, "P1", krcg_id=LOUP_KRCG_ID, name="Loup")
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert card.zone == "burned"
    actor.assert_exhausted()


def test_loup_shaped_stand_in_is_not_burned_by_a_non_toreador_vampires_successful_action():
    def loup_auto_burn(state, context):
        vampire = context["vampire"]
        if vampire.card.clan != "Toreador":
            return
        for card in active_turn_cards(state, context["actor_player"], LOUP_KRCG_ID):
            burn_turn_card(card)

    hooks.register(ACTION_SUCCEEDED_HOOK, loup_auto_burn)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Brujah")
    builder.player("P2", pool=30)
    game = builder.build()
    card = bring_turn_card_into_play(game.state, "P1", krcg_id=LOUP_KRCG_ID, name="Loup")
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert card.zone == "in_play"  # not burned: the acting vampire is not Toreador
    actor.assert_exhausted()
