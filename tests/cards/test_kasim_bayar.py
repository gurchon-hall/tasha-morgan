"""Kasim Bayar (krcg id 201598, `src/vtesbot/cards/kasim_bayar.py`).

Card text: "Camarilla Banu Haqim Justicar: Once each combat, Kasim can
discard a political action card [POLITICAL ACTION] before range is
determined to get +2 strength that combat. +1 bleed." No rulings on file.

No behavioural assertions are possible: the card is `blocked` until its
clause (2) is wired (engine support exists, ENG-046). This test only pins
the registry entry so the blocked status/reason cannot silently drift.
"""

import vtesbot.cards.kasim_bayar  # noqa: F401  (import for its registration side effect)
from vtesbot.cards import registry


def test_kasim_bayar_is_registered_as_blocked():
    reg = registry.get(201598)
    assert reg is not None
    assert reg.name == "Kasim Bayar"
    assert reg.status is registry.Status.BLOCKED


def test_blocked_reason_cites_the_engine_entry_not_a_ruling():
    reg = registry.get(201598)
    assert reg.blocked_reason is not None
    assert "ENG-046" in reg.blocked_reason
    assert not reg.blocked_reason.startswith("RUL-")  # an engine gap, not a ruling ambiguity.


def test_kasim_bayar_is_excluded_from_the_implemented_pool():
    assert 201598 not in registry.implemented_ids()
    assert 201598 in registry.blocked_ids()
