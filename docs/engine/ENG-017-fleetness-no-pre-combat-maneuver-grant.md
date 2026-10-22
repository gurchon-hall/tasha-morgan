---
status: resolved
date: 2026-10-12
cards: Fleetness
---

# ENG-017 - Fleetness - no pre-combat maneuver grant

- Situation: Fleetness's (100747) superior clause grants a vampire "1
  optional maneuver during that combat" from the moment the card is
  played (announce time) -- before whichever combat the action
  produces has even started -- but `run_combat` always starts its
  scratch state fresh and empty, with no way for an action resolving
  before combat starts to pre-seed a grant into it.
- Rules & interactions: plain text; the generic RUL-007 fizzle convention
  already covers the target-unlocked-by-resolve-time case. A
  card-module-only scratch dict was rejected as it would live outside
  `GameState`, breaking the determinism/replay invariant.
- Solution: `run_combat` gained an optional `initial_combat_state`
  parameter; `seed_pre_combat_maneuver_grant`/
  `pre_combat_maneuver_available`/`consume_pre_combat_maneuver_grant`
  are the shared helpers (a count, not a bool, so grants compose by
  addition). `ActionCardSpec` gained a `maneuver_grant` field threaded
  through both the unblocked path (a card's own `resolve()` seeds its
  direct `run_combat` call) and the blocked path
  (`perform_minion_action` seeds its own internal call). Fleetness's
  own card module is not written; the primitive is complete.
