---
status: open
date: 2026-10-23
cards: Disputed Territory
---

# ENG-062 - Disputed Territory - terms chosen after the vote

- Situation: Disputed Territory (100557) "Choose a location and a
  Methuselah. Successful referendum means the chosen Methuselah takes
  control of the chosen location." `cards/disputed_territory.py` asks for
  the location and the new controller only once `resolve_referendum`
  reports a pass, so both players vote without knowing the terms. Found
  while migrating the module to the `Card` API (step 6).
- Sources read: Rulebook §4 The Political Action: "The specific terms of
  the referendum ... are not chosen until the action itself is
  successful." Rulebook §4 The Referendum: "1. Choose the terms, if any, of
  the referendum. 2. Polling ..." Kine Resources Contested already locks
  its terms before polling (RUL-013, DES-009). User confirmation
  (2026-10-23): a political action's terms are chosen before the polling
  step.
- Needed mechanism: ask the `disputed_territory_terms` decision in
  `resolve()` before `resolve_referendum`, then apply the stored choice on
  a pass, re-checking that the location is still in play (RUL-007). This
  moves a decision earlier, so the fix gets its own commit and
  determinism run.
- Impacted code: `cards/disputed_territory.py`,
  `tests/cards/test_disputed_territory.py`.
