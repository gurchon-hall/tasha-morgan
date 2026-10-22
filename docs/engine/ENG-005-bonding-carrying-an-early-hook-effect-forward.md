---
status: resolved
date: 2026-10-10
cards: Bonding
---

# ENG-005 - Bonding - carrying an early hook effect forward

- Situation: Bonding's superior clause must produce two effects from
  one play — "+1 stealth" (usable only in the earlier block-attempt
  window) and "+1 bleed" (only readable by the later bleed-amount
  window) — and nothing in the engine let one hook application leave
  something for a later one to pick up within the same action.
- Rules & interactions: not a ruling ambiguity (ENG-003 already settled the
  action-type gating); a missing engine primitive. Applying the bleed
  bonus immediately instead (bypassing the later clamp) was rejected:
  it desynchronizes from the amount-window's floor-at-0 clamp and
  Edge-holder check, overcharging the defender in a worked example.
- Solution: `perform_minion_action` now builds a shared, mutable
  `pending: dict` before `attempt_block` runs, threaded into both the
  stealth/intercept hook context and the later bleed-amount-modifier
  context; `_perform_bleed` folds `pending[PENDING_BLEED_AMOUNT_KEY]`
  into the base amount before the clamp. Bonding was then implemented
  against both providers; a related cross-card "(limited)" bookkeeping
  gap (Threats vs. Bonding's superior clause) was fixed by re-keying
  `bleed_bookkeeping` off `pending` instead of the later-window-only
  `amount_box`. `Status.IMPLEMENTED`.
