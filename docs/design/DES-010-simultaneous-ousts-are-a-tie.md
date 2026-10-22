---
status: resolved
date: 2026-10-13
cards:
---

# DES-010 - Simultaneous ousts are a tie

- Context: two Methuselahs can reach 0 pool in one resolution (Marcos
  Belegrad's tally burn, Kine Resources Contested, double Fame torpor in
  one strike pair); the engine silently picked the first processed.
  Rulebook `5-ending-the-game.md`: "In the case of a tie there is no
  winner of the game"; EXCEPTION: a Methuselah ousted at the same time as
  their prey "gets the victory point but does not gain 6 pool counters".
  Kine Resources Contested's ruling (`data/cards/101056.json`): "If
  multiple ousts happen, players whose prey gets ousted get a victory
  point, even if they are being ousted themselves. Only the surviving
  ones get 6 pool" [LSJ 20000309].
- Decision: user ruling (project ruling, supported but not dictated by
  Rulebook §5): "oust simultané semble ok si pas de solution de
  gagner". Same event = tie, no winner; 1 VP each, no 6 pool (§5
  EXCEPTION; each is the other's prey, no last-Methuselah VP). "Same
  event" is mechanical: one card effect or one simultaneous strike pair,
  wrapped in `engine/pool.py::simultaneous_pool_losses`, which defers the
  oust check to the end of the event (`ousting.resolve_pending_ousts`).
- Consequence: `MatchResult.winner` may be `None` with `game_over`
  True (`tie`), a draw (user ruling 2026-10-13: "1 VP chacun,
  conclusion = match nul"); sim summaries count ties apart from stuck
  games. The second side of a strike pair still resolves its damage
  (mend decision) before the oust is decided.
