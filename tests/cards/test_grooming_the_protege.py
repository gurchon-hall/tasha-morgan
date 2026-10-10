"""Grooming the Protégé (krcg id 100860, `src/vtesbot/cards/
grooming_the_protege.py`).

Card text: "Move up to 3 blood from a ready vampire you control to a
younger vampire of the same clan in your uncontrolled region." No rulings
on file.

One assertion per clause/qualifier: the master-phase timing window, "a
ready vampire you control" (own, ready, blood > 0), "a younger vampire"
(strictly lower printed capacity than the source), "of the same clan",
"in your uncontrolled region" (own uncontrolled only, not the opponent's),
"up to 3 blood" (every legal amount offered, clamped by both the source's
blood and the target's remaining effective capacity), and the no-bonus-
action (not a trifle) behaviour.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.grooming_the_protege import KRCG_ID
from vtesbot.engine import CryptCard, LibraryCard
from vtesbot.engine.phases.master import master_phase

NAME = "Grooming the Protégé"


def _grooming_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="master")


def _set_clan(builder_player, instance_id: str, clan: str | None) -> None:
    """Replace the just-built vampire's `card` with one carrying `clan`
    (mirrors `test_forty_seventh_street_royals.py::_set_clan`: neither
    `ready_vampire` nor `uncontrolled_vampire` has a `clan=` parameter, and
    `CryptCard` is frozen, so a fresh instance is swapped in)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    old = vampire.card
    vampire.card = CryptCard(
        krcg_id=old.krcg_id,
        name=old.name,
        capacity=old.capacity,
        group=old.group,
        clan=clan,
        disciplines=old.disciplines,
    )


def test_registered_as_implemented_against_the_master_phase_play_hook():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=3)
    p1.uncontrolled_vampire("U1", capacity=2, blood=0)
    _set_clan(p1, "V1", "Brujah")
    _set_clan(p1, "U1", "Brujah")
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")  # would fail loudly if asked anything
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_not_offered_without_a_ready_vampire_with_blood():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=0)  # no blood to move
    p1.uncontrolled_vampire("U1", capacity=2, blood=0)
    p1.hand.append(_grooming_card())
    _set_clan(p1, "V1", "Brujah")
    _set_clan(p1, "U1", "Brujah")
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_not_offered_without_an_eligible_uncontrolled_target():
    """No uncontrolled vampire at all: nothing to move blood to."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=3)
    p1.hand.append(_grooming_card())
    _set_clan(p1, "V1", "Brujah")
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_not_offered_when_the_uncontrolled_vampire_is_a_different_clan():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=3)
    p1.uncontrolled_vampire("U1", capacity=2, blood=0)
    p1.hand.append(_grooming_card())
    _set_clan(p1, "V1", "Brujah")
    _set_clan(p1, "U1", "Toreador")
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_not_offered_when_the_uncontrolled_vampire_is_not_younger():
    """Same clan but equal (not strictly lower) capacity: not "younger"."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=3)
    p1.uncontrolled_vampire("U1", capacity=5, blood=0)
    p1.hand.append(_grooming_card())
    _set_clan(p1, "V1", "Brujah")
    _set_clan(p1, "U1", "Brujah")
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_not_offered_for_the_opponents_uncontrolled_vampire():
    """ "Your uncontrolled region" -- the opponent's own uncontrolled vampire,
    even if same-clan and younger, is not a legal target."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=3)
    p1.hand.append(_grooming_card())
    _set_clan(p1, "V1", "Brujah")
    p2 = builder.player("P2", pool=30)
    p2.uncontrolled_vampire("U1", capacity=2, blood=0)
    _set_clan(p2, "U1", "Brujah")
    game = builder.build()
    agent = ScriptedAgent("P1")
    game.state.agents["P1"] = agent
    game.state.agents["P2"] = ScriptedAgent("P2")

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_moves_the_chosen_amount_of_blood_between_the_two_vampires():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=3)
    p1.uncontrolled_vampire("U1", capacity=4, blood=0)
    p1.hand.append(_grooming_card())
    _set_clan(p1, "V1", "Brujah")
    _set_clan(p1, "U1", "Brujah")
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "grooming_the_protege:V1:U1:2")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert game.blood_of("V1") == 1
    assert game.blood_of("U1") == 2
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    agent.assert_exhausted()


def test_every_legal_amount_up_to_3_is_offered_as_a_separate_choice():
    """ "Up to 3 blood": every amount from 1 to the clamp is its own legal
    choice, not just the maximum."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=5)
    p1.uncontrolled_vampire("U1", capacity=4, blood=0)
    p1.hand.append(_grooming_card())
    _set_clan(p1, "V1", "Brujah")
    _set_clan(p1, "U1", "Brujah")
    builder.player("P2", pool=30)
    game = builder.build()

    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "master_phase_action":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    agent = RecordingAgent("P1")
    agent.expect("master_phase_action", "pass")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert seen == [
        [
            "grooming_the_protege:V1:U1:1",
            "grooming_the_protege:V1:U1:2",
            "grooming_the_protege:V1:U1:3",
            "pass",
        ]
    ]
    agent.assert_exhausted()


def test_amount_is_clamped_by_the_sources_own_blood():
    """Source has only 2 blood: "up to 3" never offers moving more than the
    source actually has."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=2)
    p1.uncontrolled_vampire("U1", capacity=4, blood=0)
    p1.hand.append(_grooming_card())
    _set_clan(p1, "V1", "Brujah")
    _set_clan(p1, "U1", "Brujah")
    builder.player("P2", pool=30)
    game = builder.build()

    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "master_phase_action":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    agent = RecordingAgent("P1")
    agent.expect("master_phase_action", "pass")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert seen == [
        [
            "grooming_the_protege:V1:U1:1",
            "grooming_the_protege:V1:U1:2",
            "pass",
        ]
    ]
    agent.assert_exhausted()


def test_amount_is_clamped_by_the_targets_remaining_capacity():
    """Target already has 1 blood out of capacity 2: room for only 1 more,
    even though both the source's blood and the "up to 3" limit allow more."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=5)
    p1.uncontrolled_vampire("U1", capacity=2, blood=1)
    p1.hand.append(_grooming_card())
    _set_clan(p1, "V1", "Brujah")
    _set_clan(p1, "U1", "Brujah")
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "grooming_the_protege:V1:U1:1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert game.blood_of("V1") == 4
    assert game.blood_of("U1") == 2
    agent.assert_exhausted()


def test_not_offered_when_the_target_is_already_at_capacity():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=3)
    p1.uncontrolled_vampire("U1", capacity=2, blood=2)  # already full
    p1.hand.append(_grooming_card())
    _set_clan(p1, "V1", "Brujah")
    _set_clan(p1, "U1", "Brujah")
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_is_not_a_trifle_no_bonus_master_phase_action():
    """`trifle is False` per krcg: a second copy played in the same master
    phase is *not* offered a bonus action from this card's own effect."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=3)
    p1.uncontrolled_vampire("U1", capacity=4, blood=0)
    p1.hand.append(_grooming_card())
    p1.hand.append(_grooming_card())
    _set_clan(p1, "V1", "Brujah")
    _set_clan(p1, "U1", "Brujah")
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "grooming_the_protege:V1:U1:1")
    # only one master phase action total: the base action, no trifle bonus.
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert len(game.state.players["P1"].hand) == 1  # second copy still in hand
    agent.assert_exhausted()


def test_replacement_is_drawn_from_the_library_after_playing():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=3)
    p1.uncontrolled_vampire("U1", capacity=4, blood=0)
    p1.hand.append(_grooming_card())
    p1.library_cards(["Filler"])
    _set_clan(p1, "V1", "Brujah")
    _set_clan(p1, "U1", "Brujah")
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "grooming_the_protege:V1:U1:1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert [c.name for c in game.state.players["P1"].hand] == ["Filler"]
    agent.assert_exhausted()
