# 2P variant pages snapshot changelog

Local, versioned cache of the two VEKN 2P-variant pages under
`data/sources/2p-variant/<fetch-date>/` (the variant rules page and the
updates log page) — same purpose and caveats as
`data/sources/rulebook/CHANGELOG.md`: a cache for routine lookups, not a
substitute for a live re-fetch when precision matters (`rules-auditor`,
Open Question resolution).

Note this is distinct from `data/formats/2p/CHANGELOG.md`, which tracks
the **allowed-card list** (`format-curator`'s domain, machine-checked
legality data). This changelog tracks the **prose rules pages** (variant
rules text + the updates log's own wording).

## 2026-10-09 — initial snapshot

Fetched both pages (raw HTML via `curl`, converted to markdown locally,
not via a summarizing fetch tool).

| Page | VEKN `dateModified` |
| --- | --- |
| 2P Variant (`655-two-player-variant...`) | 2025-05-20 |
| 2P Format Updates (`675-two-player-format-updates`) | 2026-10-03 |

Both dates match what CLAUDE.md §3 already cites for the 2P variant —
no drift found at this sync.
