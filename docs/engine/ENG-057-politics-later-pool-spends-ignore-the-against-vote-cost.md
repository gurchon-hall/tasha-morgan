---
status: open
date: 2026-10-23
cards: Marcos Belegrad; Oxford University, England
---

# ENG-057 - Politics - later pool spends ignore the against-vote cost

- Situation: `engine/politics.py::_cast_votes` checks
  `VOTE_AGAINST_POOL_COST` (Marcos Belegrad's tally burn) only when the
  "against" vote is offered; nothing reserves that pool afterwards
  (`pending["pool_reserve"]` is set only by Kine Resources Contested). A
  Methuselah who already voted against can then burn pool for Oxford votes
  down to the amount the tally burn takes, and is ousted at tally by their
  own choices. Reproduced: P2 at 2 pool votes against Marcos's referendum,
  burns 1 for Oxford, and is ousted at tally. Found by `rules-auditor`
  reviewing ENG-052.
- Sources read: DES-009 ("any choice whose consequence, even downstream,
  would take the chooser to 0 is not offered"); Marcos Belegrad's module
  and RUL-005.
- Needed mechanism: once an against vote commits a later pool cost, add
  it to that player's `pool_reserve` for the rest of the referendum, so
  `variable_pool_burn_vote_options` and later gates see it.
- Impacted code: `engine/politics.py::_cast_votes`; Marcos Belegrad and
  Oxford tests.
