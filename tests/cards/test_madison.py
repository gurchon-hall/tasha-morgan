"""Madison (krcg id 201557, `src/vtesbot/cards/madison.py`).

Card text: "Camarilla." No title, no rulings on file -- a bare sect
keyword with no further clause, confirmed against the installed `krcg`
package and the live API snapshot (`"title": null`). There is no behaviour
to exercise, so this test only proves the registration (no hooks
registered, matching the module's own "nothing left to implement" claim)
and re-confirms, from the same krcg source the implementation module
cites, that the card really does carry no title and no other clause.
"""

from vtesbot.cards import registry
from vtesbot.cards.madison import KRCG_ID

NAME = "Madison"


def test_registered_as_implemented_with_no_hooks():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.hooks == ()
    assert reg.blocked_reason is None


def test_krcg_confirms_no_title_and_no_other_clause():
    import krcg

    card = krcg.load()[KRCG_ID]
    assert card.text.strip() == "Camarilla."
    assert card.title is None
    assert card.rulings == []
