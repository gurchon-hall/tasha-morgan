"""Octane (krcg id 201609, `src/vtesbot/cards/octane.py`).

Card text: "Anarch." No title, no rulings on file -- a bare sect keyword
with no further clause, confirmed against the installed `krcg` package
(`krcg.vtes.VTES[201609].card_text == "Anarch."`, `.rulings == []`) and the live
API snapshot (`data/cards/201609.json`, `"title": null`). There is no
behaviour to exercise, so this test only proves the registration (no hooks
registered, matching the module's own "nothing left to implement" claim)
and re-confirms, from the same krcg sources the implementation module cites,
that the card really does carry no title and no other clause.
"""

from krcg.vtes import VTES

from vtesbot.cards import registry
from vtesbot.cards.octane import KRCG_ID

NAME = "Octane"


def test_registered_as_implemented_with_no_hooks():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.hooks == ()
    assert reg.blocked_reason is None


def test_krcg_confirms_no_title_and_no_other_clause():
    VTES.load()
    card = VTES[KRCG_ID]
    assert card.card_text.strip() == "Anarch."
    assert card.title is None
    assert card.rulings == []
