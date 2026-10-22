---
status: resolved
date: 2026-10-11
cards: Line Brawl; Enchant Kindred
---

# RUL-007 - Action-card target chosen at announce vs. resolve time

- Situation: `line_brawl.py`'s `[pot]` clause ("Enter combat with a
  minion") picked its target inside `resolve()`, after the
  block-attempt window had already run — the defender was asked to
  block before the specific minion that would be forced into combat
  was ever fixed.
- Rules & interactions: Rulebook §4 "Announce the Action": "All details
  of the action are defined when the action is announced, including
  the target(s)"; this engine's own `ActionCardSpec` contract already
  documented the same. The general "fizzle" ruling (target no longer
  eligible at resolve time ⇒ cost paid, successful, no effect — never
  re-picked) confirms a target is fixed once, at announce, and only
  re-validated later.
- Solution: both `line_brawl.py` and `enchant_kindred.py`'s own
  clauses now choose their target inside `apply()` (announce time),
  with `resolve()` only looking up the already-chosen id. Any future
  Action card targeting a specific minion must do the same.
