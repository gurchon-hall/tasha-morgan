---
status: resolved
date: 2026-10-22
cards: Dust Up; Slam
---

# ENG-048 - Strike damage carries no properties

- Situation: a strike resolved to a bare damage amount, always applied as
  normal damage, so the engine could not express an aggravated strike, and
  Dust Up / Slam rebuilt "hand strike at +N" from a number, keeping only
  the amount of the base damage. Found by `rules-auditor` reviewing the
  card authoring API.
- Rules & interactions: Dust Up and Slam: "Additional damage inherits all
  of the properties of the base damage." [TOM 19960225]. Rulebook §4: a
  plain hand strike deals normal, dodgeable damage equal to strength. Body
  Flare's own strike is aggravated; Dawn Operation can make all combat
  damage aggravated (ENG-049). Neither is implemented, so today a hand
  strike's base damage is always normal.
- Solution: `engine/combat.py::StrikeDamage` gains `aggravated`;
  `_resolve_one_strike` / `_resolve_strike_pair` carry the whole
  `StrikeDamage` and `_apply_strike` passes it to `apply_damage` as normal
  or aggravated. `hand_strike_damage(...)` returns the plain hand strike's
  damage with its properties; `cards/dust_up.py` and `cards/slam.py` build
  their strikes from it with `dataclasses.replace`. Covered by
  `tests/rules/test_strike_damage_properties.py`.
