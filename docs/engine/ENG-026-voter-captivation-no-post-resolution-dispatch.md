---
status: resolved
date: 2026-10-14
cards: Voter Captivation
---

# ENG-026 - Voter Captivation - no post-resolution dispatch

- Situation: Voter Captivation (krcg id 102131): "Only usable after
  resolution of a political action whose referendum passed. [pre] This
  vampire gains 1 blood for each vote by which the referendum passed."
  `cards/registry.py::Hook.REFERENDUM_RESOLVED` was reserved for exactly
  this moment but had no engine dispatch call site — a moment strictly
  after a political-action card's own `resolve()` closure (which itself
  calls `resolve_referendum` and then runs its own pass effects) fully
  returns, later than `POLLING_STEP`/`REFERENDUM_TALLIED`.
- Rules & interactions: a missing engine primitive, not a ruling question —
  the hook's own trigger semantics were already settled when it was
  named/reserved.
- Solution: `engine/politics.py::resolve_referendum` gained an optional
  `action_pending` parameter, writing its own tally/pass-fail outcome into
  `REFERENDUM_RESULT_KEY` inside whatever dict it is given (never its own
  internal polling-step `pending` scratch); `cards/kine_resources_
  contested.py`/`cards/parity_shift.py` now pass their own `resolve()`
  closure's `pending` through as `action_pending` (both still
  `Status.IMPLEMENTED`, no new provider registered). `engine/action.py::
  perform_minion_action` dispatches the new `REFERENDUM_RESOLVED_HOOK`
  (`hooks.resolve_impulse_window`, a real two-sided window — unlike
  `ACTION_SUCCEEDED_HOOK`, this is a card a player chooses to play) right
  after its own `resolve(pending)` returns, only when `action ==
  ACTION_POLITICAL` and the referendum passed; context carries
  `caller`/`other`/`caller_vampire_id`/`margin`/`pending` (the last added
  in a later pass, a per-action once-per-minion cap, `rules-auditor`
  finding). Voter Captivation's own card module (`cards/
  voter_captivation.py`, `Status.IMPLEMENTED`) was written in a later
  pass.
