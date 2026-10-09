"""Oxford University, England (Master). krcg id 101341.

Card text (fetched via krcg 5.14+, `krcg.load()[101341].text`, 2026-10-09):
    "Unique location.
    You can lock this card and burn X pool during the polling step of a
    political action to get +2X votes."

Status: blocked (OQ-6). Its only ability fires "during the polling step of a
political action", gated by OQ-6 the same as this pool's other polling-step
cards (`docs/OPEN_QUESTIONS.md`, `engine/politics.py`). It is additionally a
"location" card, a generic entity the engine does not model at all yet (no
other blocker on this card alone -- noted for when OQ-6 is resolved).
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

register(
    CardRegistration(
        krcg_id=101341,
        name="Oxford University, England",
        status=Status.BLOCKED,
        hooks=(Hook.POLLING_STEP, Hook.LOCATION_ENTITY, Hook.MASTER_PHASE_PLAY),
        source=__name__,
        blocked_reason="OQ-6",
    )
)
