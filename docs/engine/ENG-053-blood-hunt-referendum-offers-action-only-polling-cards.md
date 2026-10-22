---
status: open
date: 2026-10-23
cards: Perfect Paragon; Scalpel Tongue; Oxford University, England
---

# ENG-053 - Blood Hunt referendum offers action-only polling cards

- Situation: `engine/diablerie.py` runs the Blood Hunt through
  `resolve_referendum` with the diablerist as caller, and the
  `POLLING_STEP` contexts carry nothing that marks it. Perfect Paragon and
  Scalpel Tongue (action modifiers / reaction) and Oxford University
  ("of a political action") are offered there; a Perfect Paragon played
  there counts. Found by `rules-auditor` reviewing ENG-051.
- Sources read: Rulebook §4 The Blood Hunt: "This referendum is not an
  action, so it cannot be blocked, and action modifiers and reaction cards
  cannot be played." Card texts: "Only usable during the polling step of a
  political action" (Perfect Paragon 101387, Scalpel Tongue 101686);
  Oxford "during the polling step of a political action" (101341).
- Needed mechanism: a `POLLING_STEP` context key saying whether the
  referendum comes from a political action, read by these providers; the
  `diablerie.py` comment claiming action modifiers are excluded "for free"
  is wrong and goes with it.
- Impacted code: `engine/politics.py`, `engine/hook_contexts.py`,
  `engine/diablerie.py`; the three card modules.
