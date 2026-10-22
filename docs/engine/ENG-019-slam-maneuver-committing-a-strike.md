---
status: resolved
date: 2026-10-12
cards: Slam
---

# ENG-019 - Slam - maneuver committing a strike

- Situation: Slam's (101798) superior clause bundles its maneuver with
  its own "hand strike at +2 damage" effect ("as above") — a genuine
  "maneuver from a strike" (per RUL-008's resolution): using it must
  commit that combatant's one strike choice for the round to this same
  effect, with no independent later choice. No mechanism existed for a
  maneuver grant to pre-commit the strike step.
- Rules & interactions: Rulebook §4 Choose Strike, verbatim, quoted in
  RUL-008's own resolution; [LSJ 20021028] confirms the maneuver and
  strike are not independent for this card.
- Solution: added `COMMITTED_STRIKE_KEY` inside the round-scoped
  `round_state`; `commit_strike_for_round(context, strike)` (called
  from a strike-bundled `MANEUVER_HOOK` provider's own grant; raises
  if called twice for the same vampire the same round, or if its
  choice-value collides with a built-in strike value); `_ask_strike`
  pops (not reads) the commitment before offering anything, locking
  only the *initial* strike of the round, not a later additional
  strike. A plain, non-strike-bundled maneuver (Saku, Pursuit, Dance
  with the Devil, Fleetness) is unaffected. Slam itself was then
  implemented against this mechanism (both clauses).
  `Status.IMPLEMENTED`.
