---
status: open
date: 2026-10-15
cards:
---

# RUL-014 - Politics - Blood Hunt referendum polling order

- Situation: `rules-auditor`, reviewing the new diablerie-resolution
  subsystem (`engine/diablerie.py::resolve_diablerie`), flagged that
  the mandatory, automatic Blood Hunt referendum (Rulebook §4
  "Diablerie" > "The Blood Hunt") has no card cast to establish a
  natural "caller" with impulse first (Rulebook §2 Sequencing). Every
  other referendum this engine resolves is reached only via an
  actually-cast political action card. `resolve_diablerie` picks the
  diablerist's own controller as `resolve_referendum`'s `caller_player`
  (so she polls first), reasoning that impulse "returns to the acting
  Methuselah" of the triggering minion action (the diablerie attempt
  itself). Does not affect vote-source correctness (RUL-005's resolved
  mechanism, and this call's own `include_caller_card_vote=False` fix,
  are both symmetric regardless of who is nominally "caller") -- only
  who polls first.
- Sources read: Rulebook §4 "Diablerie"/"The Blood Hunt" (live-fetched
  2026-10-15, matching cached `data/sources/rulebook/2026-10-09/
  4-detailed-turn-sequence.md:1076-1118` verbatim): "a referendum is
  automatically and immediately conducted... Otherwise, this
  referendum is handled just like any other" -- settles that normal
  polling/tally happens, but states no explicit polling-order rule for
  a referendum with no calling card. Rulebook §2 Sequencing (impulse
  returns to the acting Methuselah) checked but not card/mechanism-
  specific enough to close this without inference.
- Candidate readings: (A) diablerist's controller polls first, as
  currently implemented (impulse-returns-to-acting-Methuselah
  reading). (B) some other fixed order (e.g. victim's controller
  first, as the one "responding" to being diablerized). No source
  found contradicting (A) or mandating (B); flagged as non-blocking by
  `rules-auditor` since no implemented card's text currently depends
  on Blood Hunt polling order.
- Impacted code/cards: `src/vtesbot/engine/diablerie.py`
  (`resolve_diablerie`'s call into `engine/politics.py::
  resolve_referendum`). No card currently depends on this order;
  revisit before implementing a future card whose text is sensitive to
  who polls first in this specific referendum.
