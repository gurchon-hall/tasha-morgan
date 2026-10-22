---
status: open
date: 2026-10-23
cards:
---

# ENG-055 - Casting loop alternates single steps, not rounds

- Situation: `engine/politics.py::_cast_votes` gives each Methuselah one
  step per turn (cast one source, play one option, or pass), alternating,
  and closes after two passes in a row (RUL-006). RUL-017 replaces this
  with declaration rounds.
- Sources read: RUL-017 (user ruling, Rulebook §4 Polling, §2
  Sequencing).
- Needed mechanism: within a turn, the player keeps choosing (cast a
  source, play an option) until they choose to end their declaration; the
  turn then goes to the next Methuselah. Polling closes after a full round
  in which nobody cast or played anything. Sources gained mid-cast
  (ENG-051) are castable in the same turn. The `polling_step_cast`
  choices and the bots' handling of them change; the determinism baseline
  is expected to move.
- Impacted code: `engine/politics.py::_cast_votes`; politics tests;
  `agents/` if they special-case the old pass semantics.
