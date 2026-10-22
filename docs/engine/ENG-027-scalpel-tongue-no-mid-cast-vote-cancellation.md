---
status: resolved
date: 2026-10-14
cards: Scalpel Tongue
---

# ENG-027 - Scalpel Tongue - no mid-cast vote cancellation

- Situation: Scalpel Tongue (krcg id 101686): "Only usable during the
  polling step of a political action. [cel][pre] Choose a vampire who has
  cast votes or ballots in this referendum. The chosen vampire is locked
  and abstains (this cancels the chosen vampire's votes and ballots)."
  Needed a way to retroactively undo an already-cast vote source mid-way
  through `_cast_votes`'s own casting loop — distinct from
  `pending["forced_abstain"]` (RUL-005), which only ever prevents a future
  cast, applied once before casting begins.
- Rules & interactions: ruling on file, "Cannot be used during a referendum
  that is automatically passing" [PIB 20150105]/[LSJ 19980107] — not
  itself built (no auto-passing mechanism exists in the engine yet, per
  RUL-005's own note); otherwise a missing engine primitive, not a ruling
  ambiguity.
- Solution: `engine/politics.py::_cast_votes` now also offers
  `POLLING_STEP_HOOK` on every player's own turn in the existing
  table-order rotation (RUL-006), under a new `context["phase"] ==
  "mid_cast"` value, merged into the same `"polling_step_cast"` `Decision`
  (mirrors `engine/action.py::_ask_stealth_or_decrease`'s own
  two-hooks-into-one-offer precedent); a `"mid_cast"` option's own
  `apply(state)` returns the canceled `VoteSource.source_id` instead of
  `None`. `_apply_retroactive_vote_cancellation` removes that source from
  `remaining` (if not yet cast) and its own entry from the `casts` log
  (if already cast), subtracting its votes from whichever direction it
  was cast in. The loop's former "end immediately once `remaining` is
  empty" shortcut was removed (no longer correct once a cancellation
  opportunity can exist with nothing left to cast) — a pure optimization,
  so no existing decision sequence changes. Scalpel Tongue's own card
  module (`cards/scalpel_tongue.py`, `Status.IMPLEMENTED`) was written in
  a later pass.
