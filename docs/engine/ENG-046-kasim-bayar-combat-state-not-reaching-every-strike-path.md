---
status: resolved
date: 2026-10-22
cards: Kasim Bayar
---

# ENG-046 - Kasim Bayar - combat_state not reaching every strike path

- Situation: Kasim Bayar (201598): "Once each combat, Kasim can discard a
  political action card [POLITICAL ACTION] before range is determined to
  get +2 strength that combat." A once-per-combat bonus recorded at
  Before Range must reach every later strength computation in that
  combat. `combat_state` was not threaded into `BEFORE_RANGE_HOOK` /
  `COMBAT_STRENGTH_MODIFIER_HOOK`, and Dust Up, Slam and Weighted Walking
  Stick each recomputed strike strength on their own, so such a bonus
  would silently drop when striking through one of those cards.
- Rules & interactions: a missing engine primitive, not a ruling
  ambiguity; the card has no rulings on file.
- Solution: `engine/combat.py` threads `combat_state`
  (`COMBAT_STATE_CONTEXT_KEY`) into `BEFORE_RANGE_HOOK`,
  `COMBAT_STRENGTH_MODIFIER_HOOK` and `COMBAT_STRIKE_OPTION_HOOK`
  contexts, and `hand_strike_strength(state, player, vampire, opponent,
  combat_state=None)` is the single "what a plain hand strike deals now"
  computation: `_strike_strength`, `cards/dust_up.py`, `cards/slam.py`
  and `cards/weighted_walking_stick.py` all call it and forward
  `combat_state`. Covered by
  `tests/rules/test_combat_strength_before_range.py`. Kasim Bayar itself
  stays `blocked` until its clause (2) is wired as a
  `BEFORE_RANGE_HOOK` / `COMBAT_STRENGTH_MODIFIER_HOOK` provider pair:
  ordinary card work, no further engine change needed.
