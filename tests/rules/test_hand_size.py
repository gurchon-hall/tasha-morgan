"""Hand-size enforcement (Rulebook §2 Card Types > Drawing Cards, local
cache `data/sources/rulebook/2026-10-09/2-card-types.md`, lines 128-137):
"The number of cards in your hand should always match your hand size ...
Whenever an effect changes your hand size or adds or removes cards from
your hand, immediately discard down to or draw up to match your hand
size." `engine/hand.py::effective_hand_size`/`reconcile_hand_size` is the
mechanism; `"hand_size_modifier"` is the passive, mandatory numeric hook
(`hooks.sum_modifiers` contract) a printed ability (e.g. Carmelita
Neillson, krcg id 201625) registers against.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using trivial fake providers standing in for a real card.
Carmelita's own effect module is a separate `card-implementer` pass.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards._shared import play_from_hand_pending
from vtesbot.engine import hooks
from vtesbot.engine.format import FormatConfig
from vtesbot.engine.hand import effective_hand_size, reconcile_hand_size


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def _fake_hand_size_modifier(delta: int):
    def provider(state, context):
        return delta

    return provider


def test_effective_hand_size_defaults_to_the_format_base():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1")
    builder.player("P2")
    game = builder.build()

    assert effective_hand_size(game.state, "P1") == 7


def test_effective_hand_size_adds_a_registered_modifier():
    """Stands in for Carmelita Neillson's "+1 hand size" (krcg id 201625)."""
    hooks.register("hand_size_modifier", _fake_hand_size_modifier(1))
    builder = ScenarioBuilder(seed=1)
    builder.player("P1")
    builder.player("P2")
    game = builder.build()

    assert effective_hand_size(game.state, "P1") == 8


def test_reconcile_forces_a_discard_when_hand_exceeds_effective_size():
    """Hand size decreasing: a real `Decision` is raised for *which* card,
    since the rule mandates the discard but never says which card."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1")
    p1.hand_cards(["Alpha", "Beta"])
    builder.player("P2")
    game = builder.build()
    game.state.format = FormatConfig(hand_size=1)
    agent = ScriptedAgent("P1").expect("hand_size_discard", "discard:1")
    game.state.agents["P1"] = agent

    reconcile_hand_size(game.state, "P1")

    assert [c.name for c in game.state.players["P1"].hand] == ["Alpha"]
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Beta"]
    agent.assert_exhausted()


def test_reconcile_discards_multiple_cards_one_choice_at_a_time():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1")
    p1.hand_cards(["Alpha", "Beta", "Gamma"])
    builder.player("P2")
    game = builder.build()
    game.state.format = FormatConfig(hand_size=1)
    agent = ScriptedAgent("P1")
    agent.expect("hand_size_discard", "discard:2")  # Gamma first, re-offered each time
    agent.expect("hand_size_discard", "discard:0")  # then Alpha, out of the remaining two
    game.state.agents["P1"] = agent

    reconcile_hand_size(game.state, "P1")

    assert [c.name for c in game.state.players["P1"].hand] == ["Beta"]
    assert sorted(c.name for c in game.state.players["P1"].ash_heap) == ["Alpha", "Gamma"]
    agent.assert_exhausted()


def test_reconcile_draws_up_automatically_when_library_has_cards():
    """Hand size increasing with cards available: no `Decision`, logged the
    same way `discard_phase`'s own replacement draw is."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1")
    p1.hand_cards(["Alpha"])
    p1.library_cards(["Beta", "Gamma"])
    builder.player("P2")
    game = builder.build()
    game.state.format = FormatConfig(hand_size=3)
    game.state.agents["P1"] = ScriptedAgent("P1")  # would fail loudly if asked anything

    reconcile_hand_size(game.state, "P1")

    assert [c.name for c in game.state.players["P1"].hand] == ["Alpha", "Beta", "Gamma"]
    assert game.state.players["P1"].library == []
    random_entries = [e for e in game.state.log.entries if e.kind == "random"]
    assert [e.data["result"] for e in random_entries] == ["Beta", "Gamma"]


def test_reconcile_stops_drawing_when_library_is_empty():
    """Hand size increasing with an empty library: no draw, no crash --
    mirrors `discard_phase`'s own empty-library handling."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1")
    p1.hand_cards(["Alpha"])
    builder.player("P2")
    game = builder.build()
    game.state.format = FormatConfig(hand_size=3)
    game.state.agents["P1"] = ScriptedAgent("P1")  # would fail loudly if asked anything

    reconcile_hand_size(game.state, "P1")  # must not raise

    assert [c.name for c in game.state.players["P1"].hand] == ["Alpha"]
    assert game.state.players["P1"].library == []


def test_discard_phase_reconciles_after_a_lowered_effective_hand_size():
    """Integration: `discard_phase`'s own replacement draw is one of the two
    wired call sites -- a modifier that lowers the effective hand size mid-
    phase still gets reconciled immediately afterwards."""
    hooks.register("hand_size_modifier", _fake_hand_size_modifier(-6))  # 7 - 6 = 1
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1")
    p1.hand_cards(["Alpha", "Beta"])
    p1.library_cards(["Gamma"])
    builder.player("P2")
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("discard_phase_action", "discard:0")  # discard Alpha, draw Gamma
    agent.expect("hand_size_discard", "discard:1")  # forced down to 1: discard Gamma
    game.state.agents["P1"] = agent

    from vtesbot.engine.phases.discard import discard_phase

    discard_phase(game.state, "P1")

    assert [c.name for c in game.state.players["P1"].hand] == ["Beta"]
    assert sorted(c.name for c in game.state.players["P1"].ash_heap) == ["Alpha", "Gamma"]
    agent.assert_exhausted()


def test_play_from_hand_pending_reconciles_after_a_lowered_effective_hand_size():
    """Integration: `cards._shared.play_from_hand_pending` is the other
    wired call site -- every card play's own replacement draw goes through
    it, so a lowered effective hand size is reconciled right after any
    card play, not just the discard phase."""
    hooks.register("hand_size_modifier", _fake_hand_size_modifier(-6))  # 7 - 6 = 1
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1")
    p1.hand_cards(["Alpha", "Beta"])
    p1.library_cards(["Gamma", "Delta"])
    builder.player("P2")
    game = builder.build()
    alpha_krcg_id = game.state.players["P1"].hand[0].krcg_id
    agent = ScriptedAgent("P1").expect("hand_size_discard", "discard:1")  # discard Gamma
    game.state.agents["P1"] = agent

    played = play_from_hand_pending(game.state, "P1", alpha_krcg_id)

    assert played.name == "Alpha"
    assert [c.name for c in game.state.players["P1"].hand] == ["Beta"]
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Gamma"]
    assert [c.name for c in game.state.players["P1"].library] == ["Delta"]
    agent.assert_exhausted()
