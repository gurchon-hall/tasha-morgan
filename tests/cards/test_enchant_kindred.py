"""Enchant Kindred (krcg id 100640) -- registration-only coverage.

Blocked (OQ-17, `docs/OPEN_QUESTIONS.md`): no engine entry point lets a
library card of type "Action" (as opposed to "Action Modifier") inject a
new, self-contained minion action. See `src/vtesbot/cards/enchant_kindred.py`
for the full text/ruling analysis. Following the project's own established
pattern for a card blocked on a missing engine mechanism (e.g.
`kine_resources_contested.py`, `scalpel_tongue.py`), there is no engine
behaviour to test yet -- only that the card is correctly registered as
blocked, with a reason, and is on the active 2P allowed list it claims to
unblock.
"""

import json
from pathlib import Path

from vtesbot.cards import enchant_kindred  # noqa: F401 -- import for registration
from vtesbot.cards.registry import Status, get

KRCG_ID = 100640


def test_enchant_kindred_is_registered_blocked_with_a_reason():
    reg = get(KRCG_ID)
    assert reg is not None
    assert reg.status is Status.BLOCKED
    assert reg.blocked_reason == "OQ-17"
    assert reg.name == "Enchant Kindred"


def test_enchant_kindred_is_not_counted_as_implemented():
    from vtesbot.cards.registry import blocked_ids, implemented_ids

    assert KRCG_ID in blocked_ids()
    assert KRCG_ID not in implemented_ids()


def test_enchant_kindred_is_on_the_active_2p_allowed_list():
    data_path = Path(__file__).resolve().parents[2] / "data" / "formats" / "2p" / "2026-10-03.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    ids = {card.get("krcg_id") for card in data["cards"]}
    assert KRCG_ID in ids
