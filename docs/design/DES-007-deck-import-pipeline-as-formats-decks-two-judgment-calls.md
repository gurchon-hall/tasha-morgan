---
status: resolved
date: 2026-10-12
cards:
---

# DES-007 - Deck-import pipeline as `formats/`/`decks/`, two judgment calls

- Context: milestone 1 ("Deck import + 2P legality check") had no
  runtime implementation at all (ENG-012 Gap 1
  noted this explicitly) -- only the dev-only
  `scripts/validate_deck.py`/`scripts/krcg_match.py` used to build the
  curated `data/decks/vekn-2p/*.json` fixtures.
- Decision: built `src/vtesbot/formats/` (allowed-list loading +
  legality rules, typed port of `scripts/validate_deck.py::validate`)
  and `src/vtesbot/decks/` (text parsing, name resolution, and
  expansion to `engine.setup.DeckSpec`) per CLAUDE.md §5's own
  architecture table. `scripts/krcg_match.py`'s matching logic moved
  into `decks/name_resolution.py`; the script is now a thin CLI
  wrapper around it, so the dev tool and the production pipeline
  cannot drift apart.
- Two judgment calls made while expanding a resolved decklist into
  real `CryptCard`/`LibraryCard` instances, neither directly stated by
  a cited rule, recorded here per the same no-guessing philosophy as
  DES-004:
  1. `LibraryCard.card_type` is read from the live krcg card's own
     `types[0].value`, not from the 2P allowed-list file's `type`
     field -- the allowed-list file only distinguishes `"Crypt"` vs
     `"Library"` (checked across the full `2026-10-03.json`: exactly
     two `type` values appear), too coarse for the engine's existing
     single-granular-type convention (`cards/modius.py`,
     `engine/politics.py`). Every library card in the active 2P pool
     currently prints exactly one krcg type, so `types[0]` is
     unambiguous today; a future multi-type card on the pool would
     need this revisited (same pre-existing simplification `engine/
     cards.py::LibraryCard.card_type`'s own single-`str` shape already
     assumes).
  2. `engine.cards.derive_sect` is only called when the krcg card's
     own `types` includes `"Vampire"` -- gating out Imbued crypt
     cards, per `derive_sect`'s and `CryptCard.sect`'s own documented
     caveat that sect is a vampire-only concept. No Imbued id is
     currently on the 2P allowed list (checked 2026-10-12), so this
     gate is not yet exercised by any real deck, but is needed the
     moment one is added.
- Consequence: a future VEKN 2P update adding a multi-type library
  card or an Imbued crypt card does not silently mis-tag/mis-sect it --
  the first hits judgment call 1 as-is (first-listed type wins,
  revisit if that becomes wrong for a specific card); the second is
  already handled correctly (no sect assigned, matching the existing
  `None`-means-"does not qualify" convention).
