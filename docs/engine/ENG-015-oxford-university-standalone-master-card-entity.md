---
status: resolved
date: 2026-10-11
cards: Oxford University, England
---

# ENG-015 - Oxford University - standalone master-card entity

- Situation: Oxford University, England (101341, "Unique location...
  lock this card and burn X pool during the polling step... to get
  +2X votes") needed a generic "a Master card that stays in play,
  mutable, rather than attaching or resolving once" entity, which did
  not exist. First widened from "a standalone *Unique* location" to
  any standalone Master card, Unique or not, after the project owner
  pointed to Wider View (102180, no "Unique" clause, same shape).
- Rules & interactions: "location" is not a structured krcg card type —
  "Unique location." is free text on an ordinary Master card. A sweep
  of the full 2P allowed list found 18 cards sharing this shape (17 of
  them Unique). Contested Cards (ENG-004/ENG-009/ENG-014) applies unmodified to
  the Unique subset.
- Solution: added `MasterCardInPlay`/`engine/master_cards.py`
  (`bring_master_card_into_play`, `detect_contest_on_bring_into_play`
  — called only for cards actually printed Unique,
  `resolve_one_master_card_contest`), unlock-phase lock/unlock +
  delayed-restore wiring, `MasterCardView`/`Observation.master_cards`,
  and `engine/politics.py::variable_pool_burn_vote_options` (the
  reusable "burn X pool for Y·X votes" polling-step primitive Oxford's
  own ability needs). Deliberately not built: a `counters` field
  (needed by 6 of the 18 sweep cards) and an opponent-burn/steal
  primitive (needed by 4 more) — flagged for whichever future pass
  needs them. Oxford itself, and the other 17 sweep cards, stay
  unimplemented.
