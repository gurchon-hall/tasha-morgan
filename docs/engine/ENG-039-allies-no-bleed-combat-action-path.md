---
status: open
date: 2026-10-17
cards:
---

# ENG-039 - Allies - no bleed/combat action path

- Situation: ENG-028/ENG-030 already recorded "ally bleed/block/combat
  participation stays out of engine scope" as a deliberate design
  choice, and built only the unlock-side primitives for a future
  ally-acting path (`engine/phases/unlock.py::_unlock_own_allies`,
  `AllyInPlay.skip_next_unlock`) -- neither `engine/action.py` nor
  `engine/combat.py` has any path for an ally to initiate a bleed, be
  blocked, block, or strike. Checked against the active 2026-10-03 2P
  allowed list's 9 Ally cards: 6 of 9 need this capability to be
  implemented correctly -- Bone Shambler (102293, bleed 1), Political
  Ally (101411, bleed 3), Double Deuce (102220, bleed 1, strength 1),
  Heartrender (102327, bleed 1, strength 1 -- its own Ⓓ ability also
  needs it to be a legal actor), City Star Taxi (102234, explicit
  "can strike"/maneuver/combat text despite 0/0 stats), The Vozhd of
  Juiz de Fora (102364, strength 4, "can enter combat with a vampire
  as a Ⓓ action"), The Vozhd of Sofia (102267, strength 3, strike +
  "can enter combat with a minion as a Ⓓ action"). Only 47th Street
  Royals (102217, implemented, passive-only) and Vagabond Mystic
  (102087, unimplemented, passive lock-only ability) avoid the gap.
- Sources read: Rulebook §4 Detailed Turn Sequence (live-fetched
  2026-10-16, matches cached `data/sources/rulebook/2026-10-09/
  4-detailed-turn-sequence.md:163-166`), verbatim: "a ready vampire
  may generally perform one of two basic actions ... bleed or hunt,
  whereas a ready ally may perform only one basic action ... bleed";
  same section's Combat text has no ally-specific carve-out ("only
  ready minions can participate in combat"), and `:1021-1029`'s
  worked example has an ally striking in combat normally. krcg card
  text for all 9 Ally entries in `data/formats/2p/2026-10-03.json`,
  cross-checked.
- Candidate readings: N/A -- not a ruling ambiguity, a missing/
  deferred engine capability (same category as ENG-028/ENG-030's own
  classification).
- Impacted code/cards: `engine/action.py` (no ally action-initiation
  path), `engine/combat.py` (no ally-as-combatant path); the
  ENG-028/ENG-030 unlock-side primitives are built but unused by either.
  Blocks Bone Shambler, Political Ally, Double Deuce, Heartrender,
  City Star Taxi, The Vozhd of Juiz de Fora, The Vozhd of Sofia
  (none written yet).
