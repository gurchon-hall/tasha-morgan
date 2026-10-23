---
status: open
date: 2026-10-23
cards: Queen Anne
---

# RUL-020 - Queen Anne - is her abstention usable while she is locked

- Situation: Queen Anne (201647): "During the polling step of a referendum
  called by Anne, she can burn 1 blood to force a younger Camarilla
  vampire to abstain." `cards/queen_anne.py` offers it only while Anne is
  ready and unlocked. Calling a referendum is a political action, and
  `engine/politics.py::political_action` locks the acting vampire first,
  so in a real game Anne is always locked by then and the ability is
  never offered; only tests that place an unlocked Anne reach it. Found
  while migrating the module to the `Card` API (step 6).
- Sources read:
  - Card text and `data/cards/201647.json` (no rulings on file).
  - Rulebook §3 Locking and Unlocking: "Only unlocked minions can perform
    actions or block the actions of other minions."
  - Rulebook §3 Wording templates: "'Lock X to do Y': These effects
    require an unlocked minion to be used, they cannot be used by locked
    minions."
  - Rulebook §2 Reaction cards / §8 Reaction Card: played by a "ready,
    unlocked minion".
  - Alexa Draper [ANK 20220705] "The ability can be used while locked"
    (a different card, cited only for comparison).
- Candidate readings:
  1. Usable while locked: the rulebook restricts locked minions only from
     actions, blocking, reaction cards and "Lock X to do Y" effects, and
     this ability is none of these. Anne must still be ready (not in
     torpor). Recommended.
  2. Unlocked only (current code): would make the ability unusable in its
     own referendum, since the caller is always locked.
- Impacted code: `cards/queen_anne.py` (`_controlled_ready_unlocked_anne`),
  `tests/cards/test_queen_anne.py::test_not_offered_if_anne_is_locked`.
  To land with ENG-056 (Anne offered mid-cast, RUL-018).
