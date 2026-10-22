---
status: resolved
date: 2026-10-15
cards: Soak; Rolling with the Punches
---

# ENG-036 - Soak - no round_state in damage-prevention hook

- Situation: Soak (101817, "A vampire can play only one Soak each
  round.") and Rolling with the Punches's superior clause (101649, "Burn
  1 blood to prevent all damage from the opposing minion's strikes this
  round.") fit `DAMAGE_PREVENTION_HOOK`, but two pieces were missing.
  `apply_damage` did not thread `round_state` into the hook context, so no
  provider could keep a per-round flag; a vampire can be offered
  prevention more than once in a round (additional-strike pairs reuse the
  same `round_state`). And the hook (`hooks.offer_until_pass`) had no way
  to express "once taken, applies automatically to every later strike
  this round".
- Rules & interactions: a missing engine primitive, not a ruling
  ambiguity. Soak's rulings shape the provider: only non-aggravated
  damage, capped at what is left [RTR 20041202] [LSJ 20040812-2]
  [PIB 20130327], no option once nothing is left [LSJ 20001114]. A
  provider mutating `damage_box` at offer time, bypassing `apply`, was
  rejected as a card-side workaround (CLAUDE.md §2).
- Solution: `apply_damage` passes `ROUND_STATE_CONTEXT_KEY: round_state`
  into the `DAMAGE_PREVENTION_HOOK` context (`engine/damage.py` owns the
  key; `engine/combat.py` re-exports it), same read/write convention as
  `ADDITIONAL_STRIKE_LIMIT_KEY`; a missing `round_state` reads as "cap
  unused". `MANDATORY_FULL_PREVENTION_KEY` /
  `mandatory_full_prevention_active` /
  `mark_mandatory_full_prevention_active` (`engine/damage.py`) add a
  per-vampire, round-scoped flag that `apply_damage` checks before
  dispatching the hook, zeroing all further damage to that vampire this
  round. Soak (`cards/soak.py`) and Rolling with the Punches
  (`cards/rolling_with_the_punches.py`) are implemented against them.
