---
status: open
date: 2026-10-23
cards: Propaganda
---

# ENG-052 - Propaganda superior asks an ousted Methuselah to lock

- Situation: the Ventrue suggested-deck mirror, random agents, seeds 49,
  61 and 84 (`sim.benchmark.run_alternating`) crash with
  `InvariantViolation("forced entry ... after oust event ...")`. In
  `cards/propaganda.py`'s superior `resolve`, `lose_pool` can oust the
  target, and `force_lock_ready_unlocked_minion` then still asks that
  player to lock a minion. Found by `rules-auditor` reviewing ENG-051; the
  600-game batch used during the refactor runs no mirror match.
- Sources read: Propaganda (101495): "[PRE] As above, and the target
  Methuselah locks a ready unlocked minion they control." Rulebook §5
  Ending the Game: an ousted Methuselah leaves the game.
- Needed mechanism: stop resolving once the game is over (check
  `state.game_over` after `lose_pool`, as other resolve paths do), plus a
  mirror-match seed batch in `tests/sim/`.
- Impacted code: `cards/propaganda.py`; `tests/sim/test_bot_vs_bot.py`.
