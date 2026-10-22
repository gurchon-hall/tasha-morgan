---
status: resolved
date: 2026-10-14
cards: Weighted Walking Stick
---

# ENG-029 - Weighted Walking Stick - no "Before Range" play window

- Situation: Weighted Walking Stick (krcg id 102169, Combat): "Only usable
  before range is determined during the first round. Put this card with 5
  counters on it on this minion; it becomes a melee weapon equipment that
  can strike: strength+1 damage. For each damage inflicted by this strike
  (even if prevented), burn 1 counter from this card." Combat Sequence step
  1 ("Before Range: Play cards before range is chosen") had no call site,
  hook, or round/combat-scoped state at all in `engine/combat.py::
  run_combat` — distinct from, and strictly before, step 2 "Determine
  Range" (maneuvers, already built, ENG-017/RUL-008/ENG-019).
- Rules & interactions: plain card text and the Combat Sequence step
  ordering; no ruling bears on the engine shape. `engine/cards.py::
  CardAttachment` already carries `counters`, and `COMBAT_STRIKE_OPTION_
  HOOK`'s existing provider contract (pre-prevention, post-reduction
  damage) already supplies what "for each damage inflicted ... even if
  prevented" needs — neither needed a change.
- Solution: added `Hook.BEFORE_RANGE`/`engine/combat.py::BEFORE_RANGE_HOOK`,
  dispatched via `_ask_before_range` (the same two-sided `hooks.
  resolve_impulse_window` shape as `END_OF_ROUND_HOOK`, acting combatant's
  controller first, RUL-002) exactly once per combat, gated by a local
  `before_range_offered` flag so it never re-fires on a later round of the
  same combat. A provider's own `apply(state)` attaches a card directly
  (`engine/attachments.py::attach_card`, mirroring `cards/celerity.py`'s
  non-unique-attachment pattern); the strike/counter-burning half needs no
  further engine change, confirmed above. Weighted Walking Stick's own card
  module is now implemented against this mechanism (`cards/
  weighted_walking_stick.py`, `Status.IMPLEMENTED`).
