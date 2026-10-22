---
status: resolved
date: 2026-10-13
cards: Perfect Paragon
---

# RUL-009 - Perfect Paragon family - proactive-only or also reactive

- Situation: ENG-021's mechanism only offers `INTERCEPT_DECREASE_HOOK`
  proactively (before a candidate is fixed, or on a retry) — never
  reactively, at the exact impulse-return moment inside the ping-pong
  where a specific candidate is already fixed and about to succeed.
  The rulebook's general "any time before resolution" Action Modifier
  timing rule doesn't itself settle whether that entitles a reactive
  offer too.
- Rules & interactions: no source draws the proactive/reactive
  distinction explicitly; two readings were open (A: proactive-only is
  sufficient; B: a reactive offer is also required).
- Solution (user ruling, same precedent as RUL-006): Reading B — both
  opportunities coexist. `_duel_stealth_intercept`'s reactive branch
  now offers `INTERCEPT_DECREASE_HOOK`'s options merged into the same
  `Decision` as `STEALTH_MODIFIER_HOOK` (mirroring how `_ask_strike`
  already merges strike/dodge options for one offer point), under the
  pre-existing `"stealth_modifier"` decision kind so every pre-RUL-009
  test is unaffected when no decrease provider is registered. A
  reactively-activated modifier is recorded into the same persistent
  `pending` list as a proactive one, so it composes identically with
  ENG-005's retry case.
