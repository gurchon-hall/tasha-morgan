---
status: resolved
date: 2026-10-09
cards:
---

# RUL-002 - Combat press step order

- Situation: Rulebook §4 Combat names a "press" step each round but
  the condensed rules mapping didn't say who presses first.
- Rules & interactions: rulebook, fetched live, verbatim: "The acting
  minion always gets first opportunity to use cards or effects before
  the opposing minion" — stated as applying at every stage of combat,
  including press, matching the project's own impulse invariant.
- Solution: `engine/combat.py::run_combat`'s press step always orders
  `[(acting_player, acting_vampire), (blocking_player,
  blocking_vampire)]`, with no round-parity alternation.
