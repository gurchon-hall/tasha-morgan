"""Celerity (krcg id 100312, `src/vtesbot/cards/celerity.py`).

Card text: "Discipline.\nPut this card on a vampire. This vampire gets +1
level of Celerity [cel] and +1 capacity. Cannot be put on a vampire with
superior Celerity [CEL]." No rulings on file.

One assertion per clause: the master-phase (non-trifle) timing window, "a
vampire" (either player's, ready or torpor, never uncontrolled -- Rulebook
SS2 Card Types / SS8 glossary "Target"), "+1 level of Celerity [cel]" and
"+1 capacity" (via `engine/attachments.py::effective_disciplines`/
`effective_capacity`), and "Cannot be put on a vampire with superior
Celerity [CEL]" (checked against the vampire's *effective*, not merely
printed, discipline levels -- OQ-8).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.celerity import KRCG_ID
from vtesbot.engine import LibraryCard
from vtesbot.engine.attachments import effective_capacity, effective_disciplines
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.phases.master import master_phase


def _celerity_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name="Celerity", card_type="master")


def test_registered_as_implemented_against_all_three_hooks():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == "Celerity"
    assert set(reg.hooks) == {
        registry.Hook.MASTER_PHASE_PLAY,
        registry.Hook.CAPACITY_MODIFIER,
        registry.Hook.DISCIPLINE_LEVEL_MODIFIER,
    }


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")  # would fail loudly if asked anything
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_not_offered_without_any_eligible_target():
    """Only an uncontrolled vampire exists anywhere -- "uncontrolled
    region" vampires are not eligible targets by default (Rulebook SS8
    glossary "Target")."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.hand.append(_celerity_card())
    p1.uncontrolled_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")  # would fail loudly if asked anything
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_attaches_to_own_ready_vampire_granting_one_celerity_level_and_capacity():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    p1.hand.append(_celerity_card())
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "celerity:V1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    vampire = game.vampire("V1")
    assert effective_capacity(game.state, vampire) == 4
    assert effective_disciplines(game.state, vampire) == ("cel",)
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Celerity"]
    agent.assert_exhausted()


def test_can_target_the_opponents_vampire():
    """Rulebook SS2 Card Types: "A master card in play is controlled by the
    Methuselah who played it, even if it is played on a card controlled by
    another Methuselah" -- no "you control" qualifier on this card's text."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.hand.append(_celerity_card())
    builder.player("P2", pool=30).ready_vampire("V1", capacity=3)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "celerity:V1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    vampire = game.vampire("V1")
    assert vampire.controller == "P2"
    assert effective_capacity(game.state, vampire) == 4
    agent.assert_exhausted()


def test_can_target_a_torpid_vampire():
    """Rulebook SS8 glossary "Target": "Vampires in the torpor region are
    eligible targets by default"."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.hand.append(_celerity_card())
    p1.torpid_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "celerity:V1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    vampire = game.vampire("V1")
    assert effective_capacity(game.state, vampire) == 4
    agent.assert_exhausted()


def test_cannot_target_a_vampire_with_printed_superior_celerity():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.hand.append(_celerity_card())
    p1.ready_vampire("V1", capacity=3, disciplines=("CEL",))
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")  # no eligible target: would fail loudly if asked anything
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_cannot_target_a_vampire_already_at_effective_superior_celerity_via_stacking():
    """A vampire with printed *basic* Celerity plus one already-attached
    copy is effectively superior (1 printed level + 1 attached level = 2,
    capped) -- a further attach must be excluded exactly like printed
    superior (OQ-8: the legality check reads *effective*, not printed,
    discipline levels)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.hand.append(_celerity_card())
    p1.ready_vampire("V1", capacity=3, disciplines=("cel",))
    builder.player("P2", pool=30)
    game = builder.build()
    vampire = game.vampire("V1")
    vampire.attachments.append(CardAttachment(krcg_id=KRCG_ID, name="Celerity"))
    assert effective_disciplines(game.state, vampire) == ("CEL", "cel")

    agent = ScriptedAgent("P1")  # no eligible target: would fail loudly if asked anything
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_stacking_two_copies_on_a_vampire_with_no_printed_celerity_reaches_superior():
    """ "+1 level of Celerity" applied twice (two attached copies, no
    printed Celerity) reaches superior -- the only textual exclusion is
    "already [effectively] superior", which this scenario is not until the
    second copy lands."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    vampire = game.vampire("V1")

    vampire.attachments.append(CardAttachment(krcg_id=KRCG_ID, name="Celerity"))
    assert effective_disciplines(game.state, vampire) == ("cel",)
    assert effective_capacity(game.state, vampire) == 4

    vampire.attachments.append(CardAttachment(krcg_id=KRCG_ID, name="Celerity"))
    assert effective_disciplines(game.state, vampire) == ("CEL",)
    assert effective_capacity(game.state, vampire) == 5


def test_is_not_a_trifle_only_one_master_phase_action_is_granted():
    """`trifle is False`: playing it does not grant a bonus master phase
    action, unlike Life in the City -- a second copy in hand is not offered
    again this master phase."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    p1.hand.append(_celerity_card())
    p1.hand.append(_celerity_card())
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "celerity:V1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert len(game.state.players["P1"].hand) == 1  # the second copy is unused this phase
    agent.assert_exhausted()


def test_replacement_is_drawn_from_the_library_after_playing():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    p1.hand.append(_celerity_card())
    p1.library_cards(["Filler"])
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "celerity:V1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert [c.name for c in game.state.players["P1"].hand] == ["Filler"]
    agent.assert_exhausted()
