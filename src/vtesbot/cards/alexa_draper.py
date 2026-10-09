"""Alexa Draper (crypt vampire ability). krcg id 201529.

Printed text (fetched via krcg 5.14+, `krcg.load()[201529].text`,
2026-10-09): "Camarilla Prince of Melbourne: During the polling step of any
referendum, Alexa can discard a card requiring Dominate [dom] to get +1
vote." Clan Ventrue, title Prince, group 6, capacity 8.

Status: blocked (OQ-6). A polling-step vote-source ability; needs the
referendum/polling-step mechanism OQ-6 leaves open (`docs/OPEN_QUESTIONS.md`,
`engine/politics.py`). The title itself ("Prince") is already representable
as plain data (`engine/cards.py::CryptCard.title`); only the vote-tally use
of that title is OQ-6-gated.
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

register(
    CardRegistration(
        krcg_id=201529,
        name="Alexa Draper",
        status=Status.BLOCKED,
        hooks=(Hook.POLLING_STEP,),
        source=__name__,
        blocked_reason="OQ-6",
    )
)
