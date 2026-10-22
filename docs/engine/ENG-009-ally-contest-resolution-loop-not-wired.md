---
status: resolved
date: 2026-10-10
cards:
---

# ENG-009 - Ally contest resolution loop not wired

- Situation: ENG-004 added contest *detection* for allies but nothing
  let either player ever pay-or-yield to end one — once a contest
  began, it never ended.
- Rules & interactions: Rulebook §4 Advanced Rules > Contested Cards
  gives one unified pay-1-pool-per-unlock-phase-or-yield mechanism for
  every unique card; the 2P variant's crypt-card override does not
  change this cost/resolution half, only the face-down/usable half,
  and only for crypt cards.
- Solution: added `engine/allies.py::resolve_one_ally_contest` (pay
  keeps `zone="contested"`, no 2P "stays usable" exception for
  allies; yield burns the yielding copy, clears the opponent's
  `contested_with` but leaves its `zone` at `"contested"` until that
  opponent's own next unlock phase) and `_unlock_own_allies` to
  perform that delayed restore; extended the unlock phase's
  pending-effect loop to surface `"contest_ally:"` ids. Shilmulo
  Tarot's own (Equipment-side) contest tracking is flagged as a
  separate, still-open gap, out of scope here.
