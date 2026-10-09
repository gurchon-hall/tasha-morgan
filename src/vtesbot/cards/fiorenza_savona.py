"""Fiorenza Savona (crypt vampire ability). krcg id 201616.

Printed text (fetched via krcg 5.14+, `krcg.load()[201616].text`,
2026-10-09): "Camarilla: If you burn the Edge for a vote, you get +1 vote.
If you burn a political action card for a vote, you get +1 vote." Clan
Ventrue, no title, group 6, capacity 7.

Status: blocked (OQ-6). Both sentences modify a referendum's vote tally
("burn the Edge for a vote" / "burn a political action card for a vote" are
themselves generic vote-source rules named by the `vtes-rules-reference`
skill's Politics section, not Fiorenza-specific actions); there is no
polling step to modify until OQ-6 (`docs/OPEN_QUESTIONS.md`,
`engine/politics.py`) is resolved.
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

register(
    CardRegistration(
        krcg_id=201616,
        name="Fiorenza Savona",
        status=Status.BLOCKED,
        hooks=(Hook.POLLING_STEP,),
        source=__name__,
        blocked_reason="OQ-6",
    )
)
