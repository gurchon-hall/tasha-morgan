"""Marcos Belegrad (crypt vampire ability). krcg id 201702.

Printed text (fetched via krcg 5.14+, `krcg.load()[201702].text`,
2026-10-09): "Camarilla Prince of Bogota: Methuselahs casting (including
controlling a minion casting) votes or ballots against a referendum called
by Marcos burn 1 pool once results are tallied." Clan Toreador, title
Prince, group 7, capacity 8.

Status: blocked (OQ-6). "Votes ... against a referendum" presumes a
for/against split this pool's sources do not settle (see OQ-6's own
discussion of what votes are compared against); needs the referendum/vote-
tally mechanism OQ-6 leaves open (`docs/OPEN_QUESTIONS.md`,
`engine/politics.py`).
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

register(
    CardRegistration(
        krcg_id=201702,
        name="Marcos Belegrad",
        status=Status.BLOCKED,
        hooks=(Hook.POLLING_STEP,),
        source=__name__,
        blocked_reason="OQ-6",
    )
)
