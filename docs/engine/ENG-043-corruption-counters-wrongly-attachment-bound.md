---
status: resolved
date: 2026-10-18
cards: Aniel; Sergio Bueno
---

# ENG-043 - Corruption counters wrongly attachment-bound

- Situation: `cards/aniel.py`'s own corruption-counter clause (shipped
  under ENG-042) modeled "burn 1 corruption counter... from another ready
  minion" as requiring a `CardAttachment` present on the target vampire
  with a positive `counters` field -- i.e. a corruption counter could only
  exist riding on an attachment. Caught in review before any other card
  built on the same (wrong) assumption.
- Rules & interactions: verified via live `krcg.load()` text for every
  legal-2P card using the "corruption counter" keyword: Aniel (201666,
  quoted above); Sergio Bueno (201662, Anarch Baron of Santo Domingo,
  unimplemented): "Minions with 1 or more of your corruption counters must
  burn 1 blood or life to attempt to block Sergio." [LSJ 20011022: passive
  ability applies even in torpor]; The Platinum Protocol (102232, library
  Action, unimplemented): "...[pro] Put 1 corruption counter on a minion
  controlled by the target Methuselah if the bleed is successful (for 1 or
  more)." [ANK 20240706]/[LSJ 20080608]: counter target chosen at
  resolution, not declaration; [ANK 20200925]/[ANK 20211105]: placing a
  counter does not allow stealing it. Revelation of Ecstasy (101624, not
  on the active 2P list, cited only as the stale precedent that misled the
  original implementation): "...put 1 corruption counter on the target
  minion. If the number of your corruption counters on the minion equals
  or exceeds their capacity or cost, you can burn those counters to steal
  the target minion." Every one of these texts puts the counter on the
  minion itself, never on an attached card; no legal-2P card ever puts a
  corruption counter on an attachment.
- Solution: added `VampireInPlay.corruption_counters` (`engine/state.py`),
  a `dict[str, int]` keyed by the placing Methuselah's `player_id` --
  Sergio Bueno's own "YOUR corruption counters" wording is placer-scoped,
  not a flat total, even though a 2P duel (CLAUDE.md §3) only ever has one
  possible placer besides the vampire's own controller; chosen over a flat
  `int` as the more future-proof shape per the task's own direction, same
  design-call precedent as ENG-041/ENG-042. `engine/corruption.py::
  add_corruption_counters`/`burn_corruption_counters` (floored at zero,
  mirroring `engine/damage.py::add_blood`/`engine/allies.py::add_life`'s
  own capped-helper shape, here capped below instead of above) /
  `total_corruption_counters`. `cards/aniel.py`'s corruption-counter clause
  now offers one option per placer with a counter present on the targeted
  vampire, burning via `burn_corruption_counters` directly -- no attachment
  involved. `engine/phases/minion.py::build_attachment_removal_action_
  spec`'s own docstring (which had cited Revelation of Ecstasy's corruption
  counters as a precedent for reusing `CardAttachment.counters`) corrected
  to cite Weighted Walking Stick's own ammo count instead, and to note the
  new field's existence. `tests/rules/test_corruption_counters.py` proves
  the primitive generically; `tests/cards/test_aniel.py` updated to match.
  `add_corruption_counters` itself is not yet exercised by any card (no
  implemented card places a corruption counter) -- left in place for
  Sergio Bueno/The Platinum Protocol, neither built here.
