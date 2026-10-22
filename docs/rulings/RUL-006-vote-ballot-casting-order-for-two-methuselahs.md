---
status: superseded
superseded_by: RUL-017
date: 2026-10-11
cards:
---

# RUL-006 - Vote/ballot casting order for two Methuselahs

- Situation: the rulebook's "cast ... in any order" leaves the actual
  turn structure unspecified; the engine's first implementation
  asserted its own strict "impulse always returns to the caller"
  procedure was sourced from the general impulse rule, when it was
  not — that procedure in fact gave the caller an unsourced tactical
  edge (casting every source back-to-back before the opponent ever
  got a look).
- Rules & interactions: no official text specifies an
  alternation/priority rule for vote-casting order beyond "in any
  order."
- Solution (user ruling, from real-table play experience): votes are
  cast in table order — seating order, repeating laps until a full
  lap passes with nobody casting. In this 2P engine: a fixed two-seat
  rotation, caller first each lap, alternating strictly after every
  step (cast or pass) regardless of who just acted; a full lap
  completing with no casts (`consecutive_passes` reaching 2) closes
  the window.
  Superseded by RUL-017 (declaration rounds).
