---
status: resolved
date: 2026-10-23
cards:
---

# ENG-058 - ask_unless_forced skips the game-over guard

- Situation: `engine/state.py::GameState.ask` raises `GameOverError` once
  the game is over, but `ask_unless_forced` took a lone legal choice and
  logged a `forced` entry without that check. A decision asked after an
  oust then surfaced only later, as the replay invariant
  `InvariantViolation` (ENG-052's Propaganda case), or not at all outside
  `sim/`. Found by `rules-auditor` reviewing ENG-052.
- Rules & interactions: CLAUDE.md §5: a forced choice is still a decision
  point, taken without asking the agent; Rulebook §5: nothing is played
  once the game is over.
- Solution: `ask_unless_forced` raises `GameOverError` before logging, like
  `ask`. Covered by `tests/rules/test_simultaneous_ousts.py::
  test_state_forces_nothing_after_a_tie`.
