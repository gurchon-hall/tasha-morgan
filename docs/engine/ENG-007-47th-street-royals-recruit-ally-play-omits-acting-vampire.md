---
status: resolved
date: 2026-10-10
cards: 47th Street Royals
---

# ENG-007 - 47th Street Royals - recruit_ally_play omits acting vampire

- Situation: a card's clan requirement (47th Street Royals requires
  Brujah) binds to the specific minion playing it, not merely "the
  Methuselah controls some vampire of that clan" — but the
  `"recruit_ally_play"` hook's context carried no identifier for which
  of possibly several ready-unlocked vampires was acting.
- Rules & interactions: Rulebook §2 "Requirements for Playing Cards"
  draws the minion-card vs. master-card distinction explicitly; a
  minion card (which Ally cards are) binds to the acting minion
  itself.
- Solution: `_choose_and_perform_action` now also passes
  `vampire=vampire.instance_id` into the hook's offer context, letting
  a provider look up the specific acting vampire and check its clan.
  Card module itself stays `blocked` for a future pass.
