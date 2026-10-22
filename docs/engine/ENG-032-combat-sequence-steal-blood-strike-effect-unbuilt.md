---
status: open
date: 2026-10-15
cards:
---

# ENG-032 - Combat Sequence - Steal Blood strike effect unbuilt

- Situation: `rules-auditor`, auditing `engine/combat.py` generally (not
  against a specific card), found the **Steal Blood** strike effect
  (occurs before the mend damage step, even if damage is inflicted
  simultaneously) entirely unbuilt. Unlike its two siblings found in the
  same audit (Combat Ends, First Strike -- deferred,
  DES-012), Steal Blood is live in the active 2026-10-03 2P allowed list:
  Diversion (100563), Theft of Vitae (101966), Form of the Cobra
  (102224) and Hunger of Marduk (102227) are all unimplemented `Combat`
  cards printing "Strike, ranged: steal N blood or life (becoming
  blood)" -- an alternate strike resolution (blood theft instead of
  damage) that `engine/combat.py::StrikeDamage`/`_resolve_strike_pair`
  has no path for.
- Sources read: Rulebook §4 Detailed Turn Sequence (live-fetched
  2026-10-15, also cached `data/sources/rulebook/2026-10-09/
  4-detailed-turn-sequence.md:1006-1053`): Steal Blood's "before the
  mend damage step... even if damage is inflicted simultaneously"; krcg
  card text for the four cards above, cross-checked against
  `data/formats/2p/2026-10-03.json`.
- Candidate readings: N/A -- a missing engine primitive, not a ruling
  ambiguity.
- Impacted code/cards: `src/vtesbot/engine/combat.py`
  (`StrikeDamage`/`run_combat`/`_resolve_strike_pair`). Blocks Diversion,
  Theft of Vitae, Form of the Cobra, Hunger of Marduk (none written yet).
