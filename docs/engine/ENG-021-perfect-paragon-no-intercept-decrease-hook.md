---
status: resolved
date: 2026-10-13
cards: Perfect Paragon
---

# ENG-021 - Perfect Paragon - no intercept-decrease hook

- Situation: Perfect Paragon's (101387) superior clause ("Allies and
  younger vampires get -1 intercept") is played by the *acting*
  vampire to weaken a potential blocker's intercept, proactively and
  persisting for the whole action ([LSJ 20020612]: usable any time
  before resolution, no block attempt required) — but
  `INTERCEPT_MODIFIER_HOOK` is only ever offered to the *defender*,
  once a specific candidate is already fixed, as a one-shot delta. A
  sweep found 16 other unimplemented cards sharing this exact shape.
- Rules & interactions: the Rulebook glossary's Action Modifier
  definition and the quoted ruling settle who plays it and when; the
  rulebook's own stealth/intercept duration sentence means the effect
  should persist and re-apply to every later-chosen qualifying
  candidate, not just one fixed at activation time.
- Solution: added `INTERCEPT_DECREASE_HOOK`, offered to the actor at
  the top of `attempt_block`'s retry loop (before any candidate
  exists, giving ENG-005's "re-offered on retry" for free); a provider's
  `apply` appends an `ActiveInterceptDecrease(delta, qualifies)`
  predicate (never itself exposed to an agent) to `pending`;
  `_duel_stealth_intercept`'s intercept baseline is now the sum of
  every recorded modifier whose predicate matches the currently-fixed
  candidate, recomputed fresh each call (never floored at 0, per the
  rulebook). Perfect Paragon itself and the rest of the family stay
  unimplemented; the mechanism is complete. See RUL-009 for a scoping
  question this entry's own first landing left open.
