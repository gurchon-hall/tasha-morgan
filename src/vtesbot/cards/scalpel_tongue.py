"""Scalpel Tongue (Action Modifier / Reaction). krcg id 101686.

Card text (fetched via krcg 5.14+, `krcg.load()[101686].text`, 2026-10-09):
    "Only usable during the polling step of a political action.
    [cel][pre] Choose a vampire who has cast votes or ballots in this
    referendum. The chosen vampire is locked and abstains (this cancels the
    chosen vampire's votes and ballots).
    [CEL][PRE] As above, and the chosen vampire burns 1 blood."

Rulings (verbatim, via krcg):
    - "Cannot be used during a referendum that is automatically passing."
      [PIB 20150105] [LSJ 19980107]

Status: blocked (OQ-6). Entirely a polling-step card at every level; needs
the referendum/polling-step mechanism OQ-6 leaves open
(`docs/OPEN_QUESTIONS.md`, `engine/politics.py`).
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

register(
    CardRegistration(
        krcg_id=101686,
        name="Scalpel Tongue",
        status=Status.BLOCKED,
        hooks=(Hook.POLLING_STEP,),
        source=__name__,
        blocked_reason="OQ-6",
    )
)
