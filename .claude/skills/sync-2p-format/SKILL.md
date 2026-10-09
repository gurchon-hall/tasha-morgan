---
name: sync-2p-format
description: >-
  Updates the versioned VEKN two-player format data (allowed card
  list, rule deltas, suggested decklists, changelog) from the
  official VEKN pages. Use when VEKN posts a 2P update or when asked
  whether the format changed.
---

# Syncing the VEKN 2P format

## Sources

1. Updates log:
   <https://www.vekn.net/two-player-format/675-two-player-format-updates>
2. Allowed list:
   <https://www.vekn.net/two-player-format/657-list-of-allowed-cards-in-2-player-vtes>
   ("Last updated on …" at the top)
3. Variant rules:
   <https://www.vekn.net/two-player-format/655-two-player-variant-for-vampire-the-eternal-struggle>
4. Decklists: linked from <https://www.vekn.net/two-player-format>

Fetch with WebFetch. If a page cannot be reached, stop and say so; do
not reconstruct a list from memory.

## Steps

1. Read the newest entry of the updates log and the "Last updated on"
   date of the allowed list. If both match the newest file in
   `data/formats/2p/`, report "no change" and stop.
2. Build the new list from the **allowed list page** (the
   authoritative full list), not from the update diff alone. Store as
   `data/formats/2p/<YYYY-MM-DD>.json`:

   ```json
   {
     "source": "<allowed list URL>",
     "vekn_last_updated": "YYYY-MM-DD",
     "fetched_on": "YYYY-MM-DD",
     "cards": [
       {"name": "As written by VEKN", "type": "Crypt|Library",
        "krcg_id": 123456}
     ]
   }
   ```

3. Match each name to KRCG using `scripts/krcg_match.py` (run with
   the project's Python, not a one-off inline snippet — keeps
   matching reproducible across syncs):

   ```bash
   python scripts/krcg_match.py <flat name/type list>.json \
     -o <result>.json
   ```

   **Crypt group rule**: every vampire on the 2-player allowed list
   is printed at group >= 5 (confirmed by the user 2026-10-08, not
   from a VEKN source page — it governs matching, not legality text).
   The script enforces this via `--crypt-min-group` (default 5): when
   a crypt name matches several krcg printings across groups, only
   the one at group >= 5 is auto-selected; if none or more than one
   qualify, it is left unmatched with every candidate (krcg_id,
   group) listed. Never override this by picking a candidate
   yourself — surface it for user confirmation instead. Names the
   script leaves in `"unmatched"` go in a `"unmatched"` array of the
   output file and in the report; do not guess the intended card,
   even when the script's `suggested_krcg_id` looks obviously right —
   confirm with the user first (see `data/formats/2p/CHANGELOG.md`,
   2026-10-08 entry, for the precedent: typos, singular/plural drift
   and missing subtitles have all previously been confirmed this
   way).
4. Diff against the previous file; cross-check the diff with the
   updates-log entry. Any discrepancy between the two VEKN pages is
   reported to the user.
5. Re-read the variant rules page. Any rule change (not only cards)
   → summarise it and flag it for `rules-engineer`.
6. Update decklist fixtures in `data/decks/vekn-2p/` if the log lists
   decklist changes; validate each with the `deck-validation` skill.
7. Append to `data/formats/2p/CHANGELOG.md`: date, cards
   added/removed, decklist changes, rule changes, source URLs.
8. Do **not** switch the active format version in config yourself;
   tell the user what switching would make illegal or unimplemented.

## Report

- VEKN update date
- Added / removed cards (counts + names)
- Implemented cards now illegal
- Newly legal cards not implemented yet
- Rule changes
- Unmatched names / inconsistencies between VEKN pages
