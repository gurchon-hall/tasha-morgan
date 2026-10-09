# Rulebook snapshot changelog

Local, versioned cache of the VEKN rulebook pages under
`data/sources/rulebook/<fetch-date>/`, so routine engine/card work does
not need a live fetch for every lookup. This is a **cache, not a source
of truth**: `rules-auditor` (and anyone resolving an Open Question) must
still re-fetch the live page, per CLAUDE.md §2 and the
`vtes-rules-reference` skill.

Each snapshot directory is immutable once written; a re-sync adds a new
dated directory rather than overwriting. Each page file carries its own
header with the source URL, VEKN's page-level `dateModified` (from the
page's own metadata, not a project guess), and our fetch date;
`_meta.json` indexes the same per snapshot.

## 2026-10-09 — initial snapshot

Fetched all 9 rulebook sections + the Imbued appendix (raw HTML via
`curl`, converted to markdown locally — not via a summarizing fetch
tool, to keep the text verbatim).

**Finding worth flagging**: the rulebook's cover label is "Version 1.1,
October 2023" (stated once, on the Introduction page), but individual
section pages carry their own, more recent `dateModified` timestamps —
VEKN edits sections without bumping that version label. Observed at
this fetch:

| Section | VEKN `dateModified` |
| --- | --- |
| 1. Introduction | 2024-02-29 |
| 2. Card Types | 2024-04-05 |
| 3. Playing the Game | 2024-02-29 |
| 4. Detailed Turn Sequence | **2025-12-13** |
| 5. Ending the Game | 2021-02-08 |
| 6. Vampire Sects | **2025-11-16** |
| 7. Legacy Sets | **2025-11-16** |
| 8. Glossaries | 2024-02-29 |
| 9. Quick Reference | 2021-02-08 |
| Appendix: Imbued Rules | 2021-02-08 |

§4 (the section this project cites most — impulse, block attempts,
combat, politics) was last edited **2025-12-13**, well after the "v1.1
October 2023" label. The project has been citing this content as
"Rulebook v1.1 (October 2023)"; that label is VEKN's own, but it is
not a reliable freshness signal for §4, §6, §7. Treat the per-page
`dateModified` in each snapshot's header as the real version marker
going forward, not the v1.1 cover date.

To check for drift on a later sync: re-fetch a page's `dateModified`
only (cheap) and compare against the value recorded here/in
`_meta.json`; only re-fetch and re-diff the full body if it changed.
