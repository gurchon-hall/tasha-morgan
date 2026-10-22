---
status: resolved
date: 2026-10-12
cards: Organized Resistance
---

# ENG-018 - Organized Resistance - no forced-block hook

- Situation: Organized Resistance (102230)'s second clause unlocks a
  locked Anarch to force an unconditional block attempt with +1
  intercept, bypassing the normal "only when needed" ping-pong —
  `attempt_block`'s candidate list was hardcoded to ready-unlocked
  vampires only, with no way to inject a locked one, unlock it on
  choice, or skip the ping-pong.
- Rules & interactions: rulings on file ([LSJ 20090514],
  [ANK 20181122-2], [LSJ 20010714-2], [ANK 20180623]) confirm the
  block and any resulting combat happen unconditionally once chosen,
  and normal prey/predator/target restrictions still apply (already
  structurally satisfied by the 2P single-opponent collapse, RUL-001).
- Solution: added `BLOCK_CANDIDATE_INJECTION_HOOK`, offered inside
  `attempt_block`'s retry loop alongside the hardcoded ready-unlocked
  candidates (unioned via `ensure_unique_choice_values`); a chosen
  injected option's `apply` unlocks the vampire and is returned
  directly as the blocker, never routed through the stealth/intercept
  ping-pong. The first clause (+1 intercept to an Anarch) is a plain,
  clean `"intercept_modifier"` provider needing no new mechanism. Card
  module itself is not written; the mechanism is complete.
