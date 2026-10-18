"""Malachi (krcg id 201676, `src/vtesbot/cards/malachi.py`).

Card text: "Independent." No rulings on file, no title, no ability clause --
the first vampire in this pool with neither. One assertion: the registry
entry.
"""

from vtesbot.cards import registry
from vtesbot.cards.malachi import KRCG_ID


def test_registered_as_implemented_with_no_hooks():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == "Malachi"
    assert reg.hooks == ()
    assert reg.blocked_reason is None
