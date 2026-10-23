---
status: resolved
date: 2026-10-23
cards: Queen Anne
---

# RUL-020 - Queen Anne - is her abstention usable while she is locked

- Situation: Queen Anne (201647): "During the polling step of a referendum
  called by Anne, she can burn 1 blood to force a younger Camarilla
  vampire to abstain." `cards/queen_anne.py` offered it only while Anne
  was unlocked, but `engine/politics.py::political_action` locks the
  acting vampire first, so in a real game the ability was never offered.
  Found while migrating the module to the `Card` API (step 6).
- Rules & interactions: Rulebook §3 Locking and Unlocking: "Only unlocked
  minions can perform actions or block the actions of other minions."
  Rulebook §3 Wording templates: "Lock X to do Y" effects need an unlocked
  minion. Reaction cards need a "ready, unlocked minion" (§2, §8). Her
  ability is none of these. No ruling on file for the card.
- Solution (user ruling, 2026-10-23): when Anne calls the referendum she
  is acting, so she is locked by default, and she still uses her ability:
  it is neither an action modifier nor a reaction. The gate is "the
  caller vampire is this Anne", lock state ignored. Implementation lands
  with ENG-056 (RUL-018), changing `_provide_queen_anne_forced_abstain` and
  `tests/cards/test_queen_anne.py::test_not_offered_if_anne_is_locked`.
