---
status: open
date: 2026-10-23
cards: The Sleeping Mind
---

# ENG-059 - The Sleeping Mind - no "minions cannot unlock" gate

- Situation: The Sleeping Mind (101805) "[DOM] During this action, minions
  cannot unlock." `cards/sleeping_mind.py` wires only the [dom] clause, yet
  the card is registered `IMPLEMENTED`, so a superior-Dominate vampire is
  never offered [DOM]. Found while migrating the module to the `Card` API
  (step 6); the gap was recorded only in the old module docstring.
- Sources read: card text and [PIB 20150703] (wake effects stay playable;
  an unlock after action resolution, e.g. Freak Drive, is prevented).
- Needed mechanism: an action-scoped "may this minion unlock now" gate
  that every `locked = False` call site consults. Nothing in the current
  pool unlocks a minion mid-action (unlock phase, combat, diablerie and
  contest resolution only), so the clause has no effect to model until a
  card such as Freak Drive is added.
- Impacted code: `cards/sleeping_mind.py`; every engine site that unlocks
  a minion.
