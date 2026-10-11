"""Siarhei Levchenko (krcg id 201612, `src/vtesbot/cards/siarhei_levchenko.py`).

Card text: "Anarch." No title, no rulings on file -- same bare-keyword shape
as Octane (201609, `tests/cards/test_octane.py`), confirmed against the
installed `krcg` package (`krcg.vtes.VTES[201612].card_text == "Anarch."`,
`.title is None`, `.rulings == []`) and the live API snapshot
(`data/cards/201612.json`, `"title": null`). No behaviour to exercise.
"""

from krcg.vtes import VTES

from vtesbot.cards import registry
from vtesbot.cards.siarhei_levchenko import KRCG_ID

NAME = "Siarhei Levchenko"


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
