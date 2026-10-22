---
status: resolved
date: 2026-10-14
cards: Kine Resources Contested
---

# RUL-013 - Kine allocation when every split zeroes the caller

- Situation: Kine Resources Contested's caller chose the 4-point split
  after the vote; a Marcos Belegrad tally burn could leave no legal
  split (DES-009), yet the allocation is mandatory.
- Rules & interactions: Rulebook §4 "The Referendum" lists step 1
  "Choose the terms" before step 2 "Polling"; the card text and rulings
  (LSJ 20000622, 20020819) are silent on timing. User ruling
  2026-10-13: "la répartition est verrouillée avant le vote puis fenetre
  d'avant votes (poison pill par exemple, pas au format 2p) puis le vote
  a lieu puis fenetre de fin de tally pour les réactions (delaying
  tactics par exemple) puis résolution des effets du vote puis fenetre
  d'action modifier de fin d'action (voter captivation par exemple)".
- Solution: the split is chosen and locked first
  (`cards/kine_resources_contested.py`), its self share must be
  affordable (pool >= share + 1) and is passed as `pool_reserve`, so
  the vote-time gates (Marcos against-cost, Oxford burn) always leave it
  payable. Windows after the tally (reactions beyond Marcos' mandatory
  burn; `REFERENDUM_RESOLVED` for Voter Captivation) have no engine
  dispatch yet. DES-009.
