---
status: resolved
date: 2026-10-10
cards: 47th Street Royals
---

# ENG-006 - 47th Street Royals - recruit-ally action not wired

- Situation: ENG-001 built the ally representation, but no minion action
  let a player actually recruit one in a real game —
  `_choose_and_perform_action` only ever offered bleed/hunt.
- Rules & interactions: Rulebook §4 "Recruit Ally": any ready minion,
  cost as listed on the card, undirected, +1 stealth; a played card is
  set aside (not yet ash-heaped) until the action resolves, burned
  only on a block (cost not paid).
- Solution: added a "recruit ally" minion action generalizing
  `perform_minion_action` with an `on_blocked` callback (fires instead
  of `resolve` on a block, after combat), `RecruitAllySpec` as the
  hook-option contract, and `play_from_hand_pending` (card leaves hand
  immediately but isn't ash-heaped until the action resolves). Folded
  into the same top-level action-choice decision as bleed/hunt. 47th
  Street Royals' own card module stays `blocked` (its own provider is
  a follow-up); deliberately not extended to allies-as-actor (no card
  needs it, and allies aren't unlocked by the engine yet).
