# VEKN Two-Player Format — Changelog

## 2026-10-03 — initial import

No prior version to diff against. This is the first snapshot of the VEKN
2-player allowed-card list recorded in this project.

- File: `data/formats/2p/2026-10-03.json`
- VEKN "Last updated on" date (allowed list page): October 3, 2026
- Matching updates-log entry: 2026-10-03 (most recent entry at import time)
- Cards: 311 total — 113 Crypt, 198 Library
- Unmatched names (no KRCG id found): 0
  - "Spirit's Thouch, The" (Library) was initially unmatched — likely a typo
    on the VEKN page for "Spirit's Touch". User confirmed 2026-10-08:
    matched to KRCG id 101850 ("Spirit's Touch", Reaction).
- Sources:
  - Allowed list: [2P card list][2p-card-list] (VEKN page, 2026-10-03)
  - Updates log: [2P updates log][2p-updates-log] (VEKN page, 2026-10-03)
  - Variant rules: [2P variant rules][2p-variant-rules] (VEKN page,
    2026-10-03)
- KRCG library version used for matching: 4.18 (4149 cards loaded)
- No active format version was configured anywhere in the project before
  this import, so nothing was switched.
- Decklist fixtures (`data/decks/vekn-2p/`) were not created in this pass;
  see report for the list of 18 VEKN suggested-decklist pages still to
  import (including 4 new "Path" decklists added 2026-10-05, after the
  allowed-list date captured here).

## 2026-10-08 — crypt group rule + matching corrections (same file)

- **Rule (confirmed by user, not from a VEKN source page — record it anyway
  since it drives matching): every vampire on the 2-player allowed list is
  printed at group >= 5.** krcg keeps multiple printings of many vampires
  across groups and assigns the plain (un-suffixed) `vekn_name` to
  whichever printing was entered first, which is often a low-group one —
  so bare-name matching silently grabbed the wrong krcg_id for 5 vampires.
  Encoded in `scripts/krcg_match.py` (`--crypt-min-group`, default 5): a
  crypt name with several krcg printings only auto-matches when exactly
  one has group >= 5; otherwise it is left unmatched with every candidate
  (krcg_id, group) listed, never guessed.
- Fixed 5 crypt entries (wrong, low-group krcg_id -> correct, group >= 5
  krcg_id): Hesha Ruhadze 200594(G2)->201591(G6), Kalinda
  200745(G2)->201596(G6), Lucinde, Alastor 200873(G3)->201700(G7),
  Nikolaus Vermeulen 201060(G2)->201705(G6), Queen Anne
  201139(G2)->201647(G6). Card counts unchanged (113 Crypt / 198 Library).
- The same stricter script flagged 4 more names the initial import had
  matched without ever reporting them as uncertain (a gap in that first
  pass, not a data error — all 4 stored krcg_ids were already correct).
  User confirmed all 4 on 2026-10-08, notes added on each `cards` entry:
  "Tegyrius, Vizier g6" (bare "g6" suffix, no parens) -> 201654; "Bone
  Shamblers" (plural on VEKN page) -> "Bone Shambler" 102293; "Fourth
  Tradition: Accounting" (missing "The") -> 100782; "Golconda" (missing
  subtitle) -> "Golconda: Inner Peace" 100842.
- Net effect: 311 cards, 0 unmatched, same as before — only the krcg_id of
  the 5 crypt fixes actually changed; the other 4 gained a confirmation
  note with the id unchanged.

## 2026-10-09 — two more VEKN suggested decklist fixtures imported

Milestone 3 (card pool for 2-3 VEKN suggested decks): imported 2 more
decklist fixtures alongside the existing `brujah.json`, bringing the total
to 3. No allowed-list card changes in this entry (format file unchanged,
still `data/formats/2p/2026-10-03.json`).

- Picked Toreador and Ventrue (over the other 12 clan decks and 4 "Path"
  decks listed on the format hub) because they share the most library
  cards with Brujah and with each other, keeping milestone 3's card pool
  manageable: Brujah/Toreador share 7 library names, Brujah/Ventrue share
  4, Toreador/Ventrue share 9. No crypt vampires are shared across any
  pair (expected: clan-specific crypts).
- `data/decks/vekn-2p/toreador.json` — source
  [2-player decklist: Toreador](https://www.vekn.net/two-player-format/666-2-player-decklist-toreador),
  VEKN "Last updated on" May 17, 2025. 12 crypt (groups 6-7), 42 library.
  All 23 distinct names matched to a krcg_id via `scripts/krcg_match.py`
  (`--crypt-min-group 5` default), 0 unmatched. Validated LEGAL against
  `2026-10-03.json`.
- `data/decks/vekn-2p/ventrue.json` — source
  [2-player decklist: Ventrue](https://www.vekn.net/two-player-format/668-2-player-decklist-ventrue),
  VEKN "Last updated on" July 8, 2025. 12 crypt (groups 6-7), 42 library.
  All 28 distinct names matched to a krcg_id, 0 unmatched. Crypt matching
  confirmed the 2026-10-08 group->=5 disambiguation fixes still resolve
  correctly for this deck's own copies of Lucinde, Alastor (krcg_id
  201700, G7) and Queen Anne (krcg_id 201647, G6). Validated LEGAL against
  `2026-10-03.json`.
- Combined distinct card pool across all 3 fixtures (brujah, toreador,
  ventrue): 20 distinct crypt vampires, 38 distinct library cards (58
  total) — this is the pool milestone 3's card-by-card implementation
  work should target next.
- 16 VEKN suggested-decklist pages (10 remaining clan decks + 4 "Path"
  decks) are still not imported as fixtures.

## 2026-10-17 — 15 more VEKN suggested decklist fixtures imported

Scope: decklist import only (per user request), not a full re-sync of the
allowed-card list or the variant rules page — neither was re-fetched in
this pass, so no entry is made for them here.

Re-fetching the format hub ([2P format hub][2p-hub]) found **18**
suggested-decklist pages (14 clan decks + 4 "Path" decks), not the 16 (10
remaining clan + 4 Path) recorded by the 2026-10-09 entry above — that
entry's own arithmetic (10 + 4 = 14, not 16) was already off, and the hub
page's own section heading ("Suggested decklists for 12 clans") undercounts
the 14 clan links actually listed on it. Both are pre-existing
inconsistencies on the VEKN side, not something introduced here. With
`brujah.json`/`toreador.json`/`ventrue.json` already imported, **15**
pages were still missing; all 15 are imported in this entry, bringing the
total to 18 decklist fixtures.

All 15 were matched via `scripts/krcg_match.py` (`--crypt-min-group 5`
default, krcg 5.14, 4149 cards) and validated/annotated via
`scripts/validate_deck.py --annotate` against `data/formats/2p/2026-10-03.json`.

- `data/decks/vekn-2p/banu-haqim.json` — [Banu Haqim][banu-haqim-url],
  updated 2025-07-08. 12 crypt (group 6), 42 library, 0 unmatched. LEGAL.
- `data/decks/vekn-2p/gangrel.json` — [Gangrel][gangrel-url] (the page's
  own URL slug omits "-gangrel", unlike every other clan page), updated
  2025-07-08. 12 crypt (groups 5-6), 42 library, 0 unmatched. LEGAL.
- `data/decks/vekn-2p/hecata.json` — [Hecata][hecata-url], updated
  2025-06-14. 12 crypt (group 6), 42 library as published. ILLEGAL: the
  Combat card written "Martyr's Resilience" on this page uses a curly
  apostrophe (U+2019); `krcg_match.py` left it unmatched (suggested
  krcg_id 101175, "Martyr's Resilience" with a straight apostrophe) —
  needs user confirmation. Stored library total is 40/42 pending that
  confirmation (the 2 missing copies sit in the fixture's own
  `"unmatched"` array, not silently merged in).
- `data/decks/vekn-2p/lasombra.json` — [Lasombra][lasombra-url]. This page
  has no "Last updated on" text in its body (unlike every other decklist
  page checked in this entry); `vekn_last_updated` is set to 2025-04-21
  from the page's `og:modified_time` meta tag instead — flagged here since
  it is not the same kind of source as the other dates in this list. 12
  crypt (group 6), 42 library, 0 unmatched. LEGAL.
- `data/decks/vekn-2p/malkavian.json` — [Malkavian][malkavian-url]. Same
  missing-body-date issue as Lasombra; `vekn_last_updated` is likewise
  2025-04-21 from `og:modified_time`. 12 crypt (group 6), 42 library, 0
  unmatched. LEGAL.
- `data/decks/vekn-2p/ministry.json` — [Ministry][ministry-url], updated
  2025-05-17. 12 crypt (group 6), 42 library as published. ILLEGAL: "Wake
  with Evening's Freshness" on this page uses a curly apostrophe
  (U+2019), left unmatched (suggested krcg_id 102137, straight apostrophe)
  — needs user confirmation. Stored library total 40/42 pending that.
- `data/decks/vekn-2p/nosferatu.json` — [Nosferatu][nosferatu-url],
  updated 2025-05-17. 12 crypt (groups 6-7), 42 library, 0 unmatched.
  LEGAL. Note (informational, not a fixture error): the page's own
  Library sub-headers read "Reaction (10)" and "Combat (14)" but the
  cards listed under each actually total 12 and 12 — a labeling error on
  the VEKN page itself; the overall Library (42) total it states is still
  correct and matches what is stored.
- `data/decks/vekn-2p/ravnos.json` — [Ravnos][ravnos-url]. Page body text
  reads "Last updated on October 3, 2026" but its `og:modified_time` meta
  says 2026-10-05; `vekn_last_updated` uses the body text (2026-10-03),
  consistent with how every other date in this changelog was read. 12
  crypt (group 7), 42 library as published. ILLEGAL: "True Love's Face"
  (5 copies) uses a curly apostrophe, left unmatched (suggested krcg_id
  102041, straight apostrophe) — needs user confirmation. Stored library
  total 37/42 pending that, which also trips the 40-60 library-size check
  on its own.
- `data/decks/vekn-2p/salubri.json` — [Salubri][salubri-url], updated
  2025-07-08. 12 crypt (group 7), 42 library as published. ILLEGAL: this
  page has the exact same typo as the one confirmed 2026-10-08 for the
  allowed-card list — "Spirit's Thouch, The" (curly apostrophe, "Thouch"
  typo, and trailing "The") for "Spirit's Touch" (krcg_id 101850) — but
  per the no-guessing rule it is surfaced again here for this fixture
  rather than silently re-applying that prior confirmation. Stored
  library total 41/42 pending user confirmation.
- `data/decks/vekn-2p/tremere.json` — [Tremere][tremere-url], updated
  2025-05-17. 12 crypt (groups 6-7), 42 library, 0 unmatched. LEGAL.
- `data/decks/vekn-2p/tzimisce.json` — [Tzimisce][tzimisce-url], updated
  2025-05-17. 42 library, 0 unmatched. ILLEGAL: the crypt vampire written
  "Nesserian" (double "s") was left unmatched — `krcg_match.py`'s only
  candidate is krcg_id 201678, "Neserian" (single "s") — needs user
  confirmation of whether this is a VEKN page typo. Stored crypt total
  10/12 pending that, which also trips the 12-minimum crypt-size check on
  its own.
- `data/decks/vekn-2p/path-of-caine.json` — [Path of
  Caine][path-of-caine-url], a mixed-clan deck, updated 2026-10-05. 12
  crypt (group 6), 42 library, 0 unmatched. LEGAL.
- `data/decks/vekn-2p/path-of-cathari.json` — [Path of
  Cathari][path-of-cathari-url], mixed-clan, updated 2026-10-05. 12 crypt
  (group 6), 42 library, 0 unmatched. LEGAL.
- `data/decks/vekn-2p/path-of-death-and-the-soul.json` — [Path of Death
  and the Soul][path-of-death-url], mixed-clan, updated 2026-10-05. 12
  crypt (group 6), 42 library, 0 unmatched. LEGAL.
- `data/decks/vekn-2p/path-of-power-and-the-inner-voice.json` — [Path of
  Power and the Inner Voice][path-of-power-url], mixed-clan, updated
  2026-10-05. 12 crypt (group 6), 42 library, 0 unmatched. LEGAL.

Net result: **10 LEGAL**, **5 ILLEGAL pending user confirmation of a
name** (Hecata, Ministry, Ravnos, Salubri, Tzimisce — each blocked solely
by one unresolved name in its own `"unmatched"` array; none of these were
guessed or silently fixed). All `implementation_status` fields across all
18 fixtures (the 15 new ones plus a re-annotation pass on `brujah.json`,
`toreador.json`, `ventrue.json`, unchanged since no card's registry status
moved) were refreshed via `scripts/validate_deck.py --annotate`; every
crypt and library card across all 18 fixtures is currently
`not_implemented` except in `brujah.json`, `toreador.json` and
`ventrue.json`, which remain fully implemented.

Combined distinct card pool across all 18 fixtures now present: **109**
distinct crypt vampires, **148** distinct library cards (257 total) —
counting only matched `krcg_id`s; the 5 still-unmatched names above are
not included until confirmed.

[2p-hub]: https://www.vekn.net/two-player-format
[banu-haqim-url]: https://www.vekn.net/two-player-format/658-2-player-decklist-banu-haqim
[gangrel-url]: https://www.vekn.net/two-player-format/660-2-player-decklist
[hecata-url]: https://www.vekn.net/two-player-format/680-2-player-decklist-hecata
[lasombra-url]: https://www.vekn.net/two-player-format/661-2-player-decklist-lasombra
[malkavian-url]: https://www.vekn.net/two-player-format/662-2-player-decklist-malkavian
[ministry-url]: https://www.vekn.net/two-player-format/663-2-player-decklist-ministry
[nosferatu-url]: https://www.vekn.net/two-player-format/664-2-player-decklist-nosferatu
[ravnos-url]: https://www.vekn.net/two-player-format/689-2-player-decklist-ravnos
[salubri-url]: https://www.vekn.net/two-player-format/665-2-player-decklist-salubri
[tremere-url]: https://www.vekn.net/two-player-format/667-2-player-decklist-tremere
[tzimisce-url]: https://www.vekn.net/two-player-format/669-2-player-decklist-tzimisce
[path-of-caine-url]: https://www.vekn.net/two-player-format/788-2-player-decklist-path-of-caine
[path-of-cathari-url]: https://www.vekn.net/two-player-format/789-2-player-decklist-path-of-cathari
[path-of-death-url]: https://www.vekn.net/two-player-format/790-2-player-decklist-path-of-death-and-the-soul
[path-of-power-url]: https://www.vekn.net/two-player-format/791-2-player-decklist-path-of-power-and-the-inner-voice

[2p-card-list]: https://www.vekn.net/two-player-format/657-list-of-allowed-cards-in-2-player-vtes
[2p-updates-log]: https://www.vekn.net/two-player-format/675-two-player-format-updates
[2p-variant-rules]: https://www.vekn.net/two-player-format/655-two-player-variant-for-vampire-the-eternal-struggle

## 2026-10-17 — user confirmed the 5 pending unmatched names (same-day follow-up)

User confirmed, for every name the previous entry above left unmatched
(each a likely curly-apostrophe or typo mismatch against KRCG, none
guessed at the time): take the suggested `krcg_id` in each case. Per the
user, VEKN's own decklist pages are unlikely to be updated again soon, so
these were saved directly rather than re-fetched for re-confirmation.

- `data/decks/vekn-2p/hecata.json` — "Martyr's Resilience" (curly
  apostrophe, as VEKN wrote it) -> krcg_id 101175. Library now 42/42.
- `data/decks/vekn-2p/ministry.json` — "Wake with Evening's Freshness"
  (curly apostrophe) -> krcg_id 102137. Library now 42/42.
- `data/decks/vekn-2p/ravnos.json` — "True Love's Face" x5 (curly
  apostrophe) -> krcg_id 102041. Library now 42/42.
- `data/decks/vekn-2p/salubri.json` — "Spirit's Thouch, The" (same typo
  confirmed 2026-10-08 for the allowed-card list, reconfirmed here for
  this separate fixture per the no-guessing rule) -> krcg_id 101850
  ("Spirit's Touch"). Library now 42/42.
- `data/decks/vekn-2p/tzimisce.json` — crypt vampire "Nesserian" (double
  "s", as VEKN wrote it) -> krcg_id 201678 ("Neserian", single "s"). Crypt
  now 12/12.

Each entry moved from the fixture's `"unmatched"` array into its
`crypt`/`library` array with the confirmed `krcg_id`, a `"note"` recording
the discrepancy and confirmation date, and the original VEKN spelling kept
in `"name"` (same convention as the 2026-10-08 fix in
`data/formats/2p/2026-10-03.json`). Re-ran
`scripts/validate_deck.py --annotate` on all 5: **all now LEGAL**, 0
unmatched remaining across all 18 decklist fixtures.

Combined distinct card pool across all 18 fixtures: **110** distinct
crypt vampires (+1, "Neserian"), **148** distinct library cards (unchanged
— the other 4 confirmed names share a `krcg_id` already present via
another deck's library) — **258** total matched cards.
