---
status: resolved
date: 2026-10-10
cards: Bonding
---

# ENG-003 - Bonding - stealth_modifier omits action type

- Situation: Bonding (100236)'s superior clause grants "+1 stealth,"
  usable only during a bleed action — but the `"stealth_modifier"`
  hook context carried no field saying which action (bleed vs. hunt)
  was in progress, so a provider could not correctly gate on it.
- Rules & interactions: card text and rulings ([TOM 19951109],
  [LSJ 19980824]/[RTR 19941109]) are explicit and consistent — not a
  ruling ambiguity, a missing engine capability.
- Solution: threaded an `action: str | None` discriminator through
  `perform_minion_action`/`attempt_block`/`_duel_stealth_intercept`
  into the stealth/intercept hook context and the block-attempt
  decision; production call sites pass named constants
  `ACTION_BLEED`/`ACTION_HUNT`/`ACTION_POLITICAL` (added so a future
  typo can't silently fail to match a provider's own check). Card
  itself stays `blocked` (see ENG-005 for the remaining gap).
