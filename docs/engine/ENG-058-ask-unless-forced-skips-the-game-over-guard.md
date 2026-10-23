---
status: open
date: 2026-10-23
cards:
---

# ENG-058 - ask_unless_forced skips the game-over guard

- Situation: `engine/state.py::GameState.ask` raises `GameOverError` once
  the game is over, but `ask_unless_forced` takes a lone legal choice and
  logs a `forced` entry without that check. A decision asked after an
  oust then only surfaces later, as the replay invariant
  `InvariantViolation` (ENG-052's Propaganda case), or not at all outside
  `sim/`. Other callers: `engine/action.py`, `allies.py`,
  `attachments.py`, `contests.py`, `master_cards.py`,
  `cards/kine_resources_contested.py`. Found by `rules-auditor` reviewing
  ENG-052.
- Sources read: CLAUDE.md §5 (decision points), `GameState.ask`.
- Needed mechanism: the same `game_over` check at the top of
  `ask_unless_forced`, with a test.
- Impacted code: `engine/state.py`; `tests/rules/`.
