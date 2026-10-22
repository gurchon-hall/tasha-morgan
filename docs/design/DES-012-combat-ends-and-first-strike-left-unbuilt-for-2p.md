---
status: resolved
date: 2026-10-15
cards:
---

# DES-012 - Combat Ends and First Strike left unbuilt for 2P

- Context: ENG-032 found three Combat Sequence/Strike-Effect primitives
  entirely unbuilt: Combat Ends, First Strike, Steal Blood. Checked
  against the active 2026-10-03 2P allowed list (krcg card text) and
  the 2P variant's own card-exclusion criteria (§2.1, live-fetched
  2026-10-15): Combat Ends has zero matches in the active list and is
  explicitly, permanently excluded by a stated design criterion
  ("combat cards that end combat"); First Strike also has zero matches
  but is not itself a stated exclusion criterion -- its absence is
  incidental to the current list, not guaranteed.
- Decision: both are left unhandled for now, the same way DES-011 leaves
  `FormatConfig.two_player` unread -- documented here rather than
  built, since nothing currently needs either.
- Consequence: Combat Ends can be treated as permanently out of scope
  for the 2P format. First Strike must be revisited if a future VEKN
  2P list update adds a card using it (`format-curator`/`sync-2p-format`
  sync should flag this). Steal Blood is **not** covered by this
  decision -- it is live in the current pool (Diversion, Theft of
  Vitae, Form of the Cobra, Hunger of Marduk) and stays tracked as
  ENG-032's own remaining gap.
