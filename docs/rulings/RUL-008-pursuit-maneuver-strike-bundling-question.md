---
status: resolved
date: 2026-10-12
cards: Pursuit
---

# RUL-008 - Pursuit - maneuver/strike bundling question

- Situation: Pursuit (101523, "[cel] Maneuver. / [CEL] Additional
  strike (limited).") was initially assumed to be a "maneuver from a
  strike card" (Rulebook §4: using such a maneuver commits that
  combatant's strike choice for the round, and bars a second strike
  card from maneuvering again the same round) — a shape the engine
  had no mechanism for.
- Rules & interactions: two owner-raised leads were checked against
  sources, and the second held up: the Rulebook's own Choose Strike
  section specifies the commit/cap only applies to a maneuver "from a
  strike" — i.e. bundled in the same clause as a strike effect
  (Slam's "as above", .44 Magnum's "with 1 optional maneuver...
  Strike:"). Pursuit's bare "[cel] Maneuver." clause, textually
  separate from its unrelated "[CEL] Additional strike" clause, is not
  that shape.
- Solution: Pursuit needed no new engine mechanism after all —
  implemented directly against the existing `MANEUVER_HOOK` (plain
  grant, no strike-lock, no per-combat bookkeeping) and
  `COMBAT_ADDITIONAL_STRIKE_HOOK`. `Status.IMPLEMENTED`. Slam and .44
  Magnum remain the genuine, still-unbuilt "maneuver from a strike"
  examples (tracked by ENG-019); `engine/combat.py`'s own docstring
  should be corrected to drop Pursuit from that list in a future pass.
