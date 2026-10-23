---
status: resolved
date: 2026-10-23
cards: Propaganda; The Platinum Protocol; Disputed Territory
---

# ENG-052 - Card effects - decisions asked after an oust

- Situation: card effects kept going after an oust inside their own
  resolution. Propaganda [PRE] asked the ousted player to lock a minion
  (Ventrue mirror, random agents, seeds 49, 61, 84); The Platinum Protocol
  [pro] asked for a corruption target (Ministry mirror, seeds 52, 96);
  Disputed Territory asked for its terms after Marcos Belegrad's tally burn
  ousted the Methuselah who voted against. All crashed with
  `InvariantViolation` or `GameOverError`. Found by `rules-auditor`
  reviewing ENG-051; the cross-deck batch used during the refactor played
  no mirror match.
- Rules & interactions: Rulebook §5 Ending the Game: "If you are ousted,
  all the cards you control are removed from the game"; "The game
  continues until only one Methuselah is left." Propaganda (101495):
  "[PRE] As above, and the target Methuselah locks a ready unlocked minion
  they control." The other action-card bleeds (Dominate Kine, Enchant
  Kindred, Fleetness, Line Brawl, Scouting Mission) end with `lose_pool`
  and ask nothing after it; Parity Shift and Kine Resources Contested
  already stop after the tally.
- Solution: the three `resolve` functions stop once `state.game_over` is
  set. Covered by `tests/cards/test_propaganda.py`,
  `test_the_platinum_protocol.py` and `test_disputed_territory.py`, and by
  the regression seeds in `tests/sim/test_bot_vs_bot.py`. A 100-seed
  mirror sweep of all 18 suggested decks (random and heuristic agents) is
  otherwise clean, apart from three random-agent stalls where both sides
  can still progress (Brujah 12, Lasombra 83, Tremere 87).
