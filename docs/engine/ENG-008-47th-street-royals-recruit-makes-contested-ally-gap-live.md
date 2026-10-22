---
status: resolved
date: 2026-10-10
cards: 47th Street Royals
---

# ENG-008 - 47th Street Royals - recruit makes contested-ally gap live

- Situation: with ENG-006/ENG-007 resolved, two independently-built
  2P-legal decks could both recruit their own copy of 47th Street
  Royals — making ENG-004's then-still-open uniqueness gap reachable in
  an ordinary game, not merely latent.
- Rules & interactions: same Contested Cards rule as ENG-004; shipping
  as-is would have silently created two independent, fully-visible
  `AllyInPlay` instances under two controllers instead of the
  mandated face-down/out-of-play treatment.
- Solution: resolved by ENG-004's own fix landing (contest detection on
  recruit). The remaining piece — actually *resolving* a contest once
  created (pay/yield) — was deliberately left to ENG-009. Card stays
  `blocked`.
