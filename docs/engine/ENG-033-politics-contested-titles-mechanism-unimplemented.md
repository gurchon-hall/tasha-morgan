---
status: open
date: 2026-10-15
cards:
---

# ENG-033 - Politics - Contested Titles mechanism unimplemented

- Situation: `rules-auditor`, auditing `engine/politics.py` generally,
  found that two *different-named* vampires both claiming the same
  scoped title (Prince/Baron per city, Justicar/Inner Circle per clan,
  Archbishop per city, Regent unique -- the last two confirmed live by
  a later `rules-auditor` pass once `TITLE_VOTES` was fixed to grant
  Sabbat-title votes, same gap) have no contest mechanism at all:
  `TITLE_VOTES`/`_collect_vote_sources`
  grants full votes unconditionally, with no competing-title-holder
  check, no 1-blood-per-unlock cost, no "treated as no title" suppression
  while contested. `CryptCard` also has no city/clan scope field to even
  detect this. Distinct from the already-implemented 2P same-named
  vampire exception (two copies of the same vampire -> title not
  contested, correctly built).
- Sources read: Rulebook §4 Advanced Rules "Contested Titles" (live-
  fetched 2026-10-15, cached `data/sources/rulebook/2026-10-09/
  4-detailed-turn-sequence.md:65-84`) and §6 Vampire Sects
  (`6-vampire-sects.md:30-61`) for the per-city/per-clan scoping; 2P
  variant page re-checked live 2026-10-15
  (`https://www.vekn.net/two-player-format/655-two-player-variant-for-
  vampire-the-eternal-struggle`) specifically for a 2P-specific title
  delta beyond the already-built same-named exception -- it states
  only "If two contested vampires (two copies of the same vampire)
  have a title, their title is not contested" and no other
  title-related rule. The general rulebook contested-titles mechanism
  (different-named vampires sharing a scoped title) is therefore
  unmodified in 2P and is exactly what this entry's gap is about.
- Candidate readings: N/A -- the rule itself is clear; only the
  data-modeling approach (how to add city/clan scope to `CryptCard`) is
  undecided. Confirmed latent against the active 2026-10-03 list (no two
  legal crypt cards currently share a contestable title+scope), so a
  future VEKN list update could make this live with zero code changes.
- Impacted code/cards: `src/vtesbot/engine/politics.py` (`TITLE_VOTES`,
  `_collect_vote_sources`), `src/vtesbot/engine/cards.py` (`CryptCard`).
  No card blocked yet.
