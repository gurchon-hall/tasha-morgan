"""Queen Anne (crypt vampire ability). krcg id 201647.

Printed text (fetched via krcg 5.14+, `krcg.load()[201647].text`,
2026-10-09): "Camarilla Prince of London: During the polling step of a
referendum called by Anne, she can burn 1 blood to force a younger
Camarilla vampire to abstain. After she diablerizes a vampire, she can
unlock. +1 bleed." Clan Ventrue, title Prince, group 6, capacity 10.

Three separate printed clauses (period-separated):
1. "During the polling step of a referendum called by Anne, she can burn 1
   blood to force a younger Camarilla vampire to abstain." -- needs the
   referendum/polling-step mechanism OQ-6 leaves open (`docs/
   OPEN_QUESTIONS.md`, `engine/politics.py`), plus a "younger" (generation)
   comparison the current `engine/cards.py::CryptCard` does not carry (not a
   ruling gap -- a missing data field; krcg 5.14's `CardDict` crypt-card
   object exposes no `generation` attribute, confirmed by inspection
   2026-10-09).
2. "After she diablerizes a vampire, she can unlock." -- diablerie itself
   has no engine implementation yet at all (no code under `engine/`
   implements torpor/diablerie resolution beyond the plain torpor zone
   transition in `engine/damage.py`); independent of OQ-6.
3. "+1 bleed" -- a flat, unconditional bonus; implementable next against the
   already-wired, mandatory `"bleed_amount_fixed_modifier"` hook
   (`engine/hooks.py`, `engine/phases/minion.py`) once the rest of the card
   is unblocked, same as Diana Iadanza's trailing "+1 bleed" clause.

Status: blocked overall (primary reason OQ-6; clauses 1-2 have additional,
independent gaps noted above that must also be closed before this card can
be implemented).
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

register(
    CardRegistration(
        krcg_id=201647,
        name="Queen Anne",
        status=Status.BLOCKED,
        hooks=(Hook.POLLING_STEP, Hook.DIABLERIE, Hook.BLEED_AMOUNT_FIXED_MODIFIER),
        source=__name__,
        blocked_reason="OQ-6",
    )
)
