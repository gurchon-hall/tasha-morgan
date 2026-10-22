---
status: resolved
date: 2026-10-11
cards: Wider View
---

# ENG-016 - Wider View - no influence hook, no removed zone

- Situation: Wider View (102180, Trifle, in-play via ENG-015's new
  entity)'s two transfer-costed clauses ("use 1 transfer to draw from
  crypt and remove a crypt card from the game"; "use 4 transfers to
  burn this card and gain 2 pool") needed the Influence phase to be
  card-hookable (it was a closed, hardcoded implementation) and a
  "removed from the game" zone distinct from "burned" (needed because
  the ruling "[c]ards removed from the game are public" [LSJ
  20080314] only matters for a card that may still be
  face-down/unrevealed at removal time).
- Rules & interactions: plain text and ruling; not an ambiguity.
- Solution: added `INFLUENCE_PHASE_ACTION_HOOK`, offered in
  `influence_phase` alongside the three hardcoded transfer types;
  added `Zone` value `"removed_from_game"` and
  `engine/damage.py::remove_vampire_from_game` (already public by the
  existing `visible_identity` rule, confirmed — no further Observation
  change needed). A `rules-auditor` follow-up found and fixed a MAJOR
  silent-mis-resolution risk: a hook-provided choice could collide in
  value with one of the three hardcoded choices and silently take over
  that action — fixed with a new general `hooks.
  ensure_unique_choice_values` guard (raises instead of silently
  misrouting), called wherever hook and hardcoded choices are unioned.
  Wider View's own card module is not written; both engine gaps are
  resolved.
