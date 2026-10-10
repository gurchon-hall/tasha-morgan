"""Life in the City (krcg id 101104, `src/vtesbot/cards/life_in_the_city.py`).

Card text: "Trifle.\nAdd 1 blood to a ready vampire." No rulings on file.
One assertion per clause: the master-phase/trifle timing window, "a ready
vampire" (either player, no ownership qualifier), and the blood-capacity cap
already enforced by `engine/damage.py::add_blood`.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.life_in_the_city import KRCG_ID
from vtesbot.engine import LibraryCard
from vtesbot.engine.phases.master import master_phase


def _life_in_the_city_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name="Life in the City", card_type="master")


def test_registered_as_implemented_against_the_master_phase_play_hook():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == "Life in the City"


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")  # would fail loudly if asked anything
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_not_offered_without_any_ready_vampire_anywhere():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.hand.append(_life_in_the_city_card())
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")  # would fail loudly if asked anything
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_adds_one_blood_to_own_ready_vampire_and_the_trifle_grants_an_extra_action():
    """Trifle (SS8 glossary): a successfully played trifle grants one extra
    master phase action, at most once per phase -- tested here by playing
    two copies in a single master phase (base action + the one trifle
    bonus)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    p1.hand.append(_life_in_the_city_card())
    p1.hand.append(_life_in_the_city_card())
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "life_in_the_city:V1")
    agent.expect("master_phase_action", "life_in_the_city:V1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert game.blood_of("V1") == 2
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [
        "Life in the City",
        "Life in the City",
    ]
    agent.assert_exhausted()


def test_can_target_the_opponents_ready_vampire():
    """ "Add 1 blood to a ready vampire" carries no "you control" qualifier
    (unlike many master cards): any ready vampire, either player's, is a
    legal target."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.hand.append(_life_in_the_city_card())
    builder.player("P2", pool=30).ready_vampire("V1", capacity=3, blood=0)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "life_in_the_city:V1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert game.blood_of("V1") == 1
    agent.assert_exhausted()


def test_targeting_a_vampire_already_at_capacity_still_spends_the_card():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=1, blood=1)
    p1.hand.append(_life_in_the_city_card())
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "life_in_the_city:V1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert game.blood_of("V1") == 1  # capped; the +1 fizzled
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Life in the City"]
    agent.assert_exhausted()


def test_replacement_is_drawn_from_the_library_after_playing():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    p1.hand.append(_life_in_the_city_card())
    p1.library_cards(["Filler"])
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "life_in_the_city:V1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert [c.name for c in game.state.players["P1"].hand] == ["Filler"]
    agent.assert_exhausted()
