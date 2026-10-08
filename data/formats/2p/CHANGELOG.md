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
  - Allowed list: [2P card list](https://www.vekn.net/two-player-format/657-list-of-allowed-cards-in-2-player-vtes) (VEKN page, 2026-10-03)
  - Updates log: [2P updates log](https://www.vekn.net/two-player-format/675-two-player-format-updates) (VEKN page, 2026-10-03)
  - Variant rules: [2P variant rules](https://www.vekn.net/two-player-format/655-two-player-variant-for-vampire-the-eternal-struggle) (VEKN page, 2026-10-03)
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
