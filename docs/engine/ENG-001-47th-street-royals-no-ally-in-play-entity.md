---
status: resolved
date: 2026-10-10
cards: 47th Street Royals
---

# ENG-001 - 47th Street Royals - no ally-in-play entity

- Situation: 47th Street Royals (102217, Ally, Brujah, "You can burn
  47th Street Royals to reduce a bleed against you by 3") was blocked
  — the engine had no representation of an ally in play at all.
- Rules & interactions: plain card text, not a ruling ambiguity; needs a
  minion-like entity with its own life/strength/bleed, distinct from a
  vampire, that can be brought into play, act independently, and be
  destroyed or burned by its own card text.
- Solution: added `AllyInPlay` (`engine/state.py`) and
  `engine/allies.py::recruit_ally`/`burn_ally`; the card's own
  reaction was proven against the existing `"bleed_amount_modifier"`
  hook with `burn_ally` as the cost. Also added `AllyView`/
  `Observation.allies` (an ally in the ready region is fully public,
  same as a ready vampire — Rulebook §4 Recruit Ally has no face-down
  state for an ally). Not built: the full "recruit ally" minion action
  itself (tracked as ENG-006) and ally bleed/block/combat participation.
  Card stays `blocked`.
