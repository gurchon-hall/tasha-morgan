"""Modius (crypt vampire ability). krcg id 201703.

Printed text (fetched via krcg 5.14+, `krcg.load()[201703].text`,
2026-10-09): "Camarilla Prince of Gary: During the polling step of any
referendum, Modius can discard a master card to get +1 vote." Clan
Toreador, title Prince, group 7, capacity 8.

Status: blocked (OQ-6). A polling-step vote-source ability; needs the
referendum/polling-step mechanism OQ-6 leaves open (`docs/OPEN_QUESTIONS.md`,
`engine/politics.py`).
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

register(
    CardRegistration(
        krcg_id=201703,
        name="Modius",
        status=Status.BLOCKED,
        hooks=(Hook.POLLING_STEP,),
        source=__name__,
        blocked_reason="OQ-6",
    )
)
