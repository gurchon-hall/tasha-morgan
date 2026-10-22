---
status: resolved
date: 2026-10-22
cards: Perfect Paragon; Alexa Draper; Modius; Oxford University, England
---

# ENG-051 - Polling-step vote sources played mid-cast are lost

- Situation: `engine/politics.py` offers `POLLING_STEP` before casting and
  on every casting turn (`phase: "mid_cast"`, ENG-027). Perfect Paragon,
  Alexa Draper and Modius were offered mid-cast too, but `_cast_votes`
  treated any mid-cast option as a cancellation, and vote sources were
  collected once before casting. The cost was paid and the vote never
  offered (reproduced for Perfect Paragon). Oxford University, England was
  limited to the before-cast window. Found by `rules-auditor` reviewing the
  hook context types.
- Rules & interactions: Rulebook §4 The Referendum, Polling: cards usable
  "during the polling step" but "before votes and ballots are cast" are
  used first; "then" votes are cast, and the polling stage ends only when
  all Methuselahs are finished casting. Gaining Votes, Other Cards: cards
  "that grant more votes or ballots can all be used subject to the normal
  rules of playing cards". A vote-granting card usable "during the polling
  step" therefore stays usable while votes are cast (user ruling, checked
  against the live rulebook 2026-10-22). Rulebook §4: "The same minion
  cannot play the same action modifier or reaction card more than once
  during each action."
- Solution: in `_cast_votes`, a mid-cast option's new
  `pending["extra_sources"]` entries join the remaining sources (shared
  `_extra_vote_source`), castable from the player's next step; a returned
  `source_id` is still a cancellation. Oxford drops its `before_cast` gate.
  Perfect Paragon is offered once per action: a second copy would re-add
  its already-cast source. Covered by `tests/rules/
  test_polling_mid_cast_sources.py` and the `..._while_votes_are_cast`
  tests of Perfect Paragon, Modius and Oxford.
