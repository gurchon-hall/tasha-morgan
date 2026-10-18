"""`CardAttachment.requires_discipline` (OQ-62, `docs/OPEN_QUESTIONS.md`):
a per-attachment marker, set by the attaching card module itself at
construction time, mirroring `is_equipment`'s own precedent (e.g. Aniel,
krcg 201666: "...a card requiring a Discipline from another ready
minion...").

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism* (`engine/cards.py::CardAttachment`, `engine/attachments.py::
attach_card`), not through any one card."""

from helpers import ScenarioBuilder
from vtesbot.engine.attachments import attach_card
from vtesbot.engine.cards import CardAttachment


def test_card_attachment_defaults_requires_discipline_to_false():
    attachment = CardAttachment(krcg_id=999999, name="Fake Card")

    assert attachment.requires_discipline is False


def test_card_attachment_can_be_constructed_with_requires_discipline_true():
    attachment = CardAttachment(
        krcg_id=999999, name="Fake Discipline Card", requires_discipline=True
    )

    assert attachment.requires_discipline is True


def test_attach_card_defaults_requires_discipline_to_false():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    vampire = game.vampire("V1")

    attachment = attach_card(game.state, vampire, controller="P1", krcg_id=999999, name="Fake Card")

    assert attachment.requires_discipline is False


def test_attach_card_threads_requires_discipline_true_through():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    vampire = game.vampire("V1")

    attachment = attach_card(
        game.state,
        vampire,
        controller="P1",
        krcg_id=999999,
        name="Fake Discipline Card",
        requires_discipline=True,
    )

    assert attachment.requires_discipline is True
