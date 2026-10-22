---
status: open
date: 2026-10-15
cards:
---

# ENG-035 - Politics - Prisci Block has no engine mechanism

- Situation: `rules-auditor` found `TITLE_VOTES` wrongly claimed Sabbat
  titles were "out of pool scope" (now fixed: Bishop/Archbishop/Cardinal/
  Regent added as flat per-ready-vampire vote values). Priscus does not
  fit that same flat table: §6 Vampire Sects describes "the prisci as a
  group have 3 votes," cast via its own 1-ballot-per-ready-priscus
  sub-referendum (for/against/abstain on a tie), shifting as ballots are
  cast during the main referendum's own polling step -- a group/
  block-voting mechanism, not a per-vampire `VoteSource`.
- Sources read (with URL/section): Rulebook §6 Vampire Sects, live
  re-fetch succeeded 2026-10-15 (`https://www.vekn.net/rulebook`),
  matching the local cache verbatim
  (`data/sources/rulebook/2026-10-09/6-vampire-sects.md:70-80`, fetched
  2026-10-09, `dateModified` 2025-11-16): "The prisci as a group have
  3 votes. During a referendum, the prisci block of 3 votes is cast
  'for' or 'against' the referendum according to the prisci
  sub-referendum. Each ready priscus provides 1 ballot for this
  sub-referendum, and votes may not be used in this sub-referendum.
  [...] Whichever side has the greater number of ballots in the
  sub-referendum gains 3 votes in the main referendum. If the
  sub-referendum is tied, the prisci block abstains [...] the prisci
  block of 3 votes might shift [...] as the majority in the
  sub-referendum changes."
- Candidate readings: confirmed Reading A -- the quoted text above is
  itself a description of exactly a nested sub-referendum (its own
  ballot-cast/tally loop, feeding a single for/against/abstain
  `VoteSource` into the main referendum's own tally, re-evaluated as
  ballots are cast); no "B" alternative is needed. Still unbuilt: this
  confirms the engine shape to build, it does not build it.
- Impacted code/cards: `src/vtesbot/engine/politics.py` (`TITLE_VOTES`,
  `_collect_vote_sources`, `_cast_votes`). No card blocked yet (the active
  2026-10-03 list has exactly one Priscus, krcg id 201760 Khin Aye; her own
  printed text is independent of this mechanism).
