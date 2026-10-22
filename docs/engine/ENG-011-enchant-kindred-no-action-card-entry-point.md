---
status: resolved
date: 2026-10-10
cards: Enchant Kindred
---

# ENG-011 - Enchant Kindred - no action-card entry point

- Situation: Enchant Kindred (100640, `types==["Action"]`) is itself
  the acting vampire's whole minion action for the turn — but the
  engine had no generic way for a played library card to supply its
  own alternate minion action (only Bleed/Hunt/Recruit-Ally were
  wired into `_choose_and_perform_action`).
- Rules & interactions: plain text; faking it as an Action-Modifier on a
  separately-chosen bleed would wrongly let the vampire bleed for free
  and play the card as a bonus. "A younger vampire" (superior clause)
  reads, per the project owner, as younger than the acting vampire,
  matching the unqualified-comparative convention other cards' texts
  use.
- Solution: added `ACTION_CARD_PLAY_HOOK`/`ActionCardSpec` (base
  stealth, directed/undirected, `resolve`, optional `on_blocked`, and
  an `action` field so a clause can declare its real mechanical
  identity, e.g. `ACTION_BLEED`, so it doesn't silently suppress
  another card's bleed-gated provider sharing the window), offered
  alongside the existing top-level choices. Enchant Kindred was then
  implemented: basic clause as a +2 bleed tagged `ACTION_BLEED`;
  superior clause raises a plain "pick an eligible uncontrolled
  vampire" decision and adds blood via `effective_capacity` (ENG-002).
  `Status.IMPLEMENTED`.
