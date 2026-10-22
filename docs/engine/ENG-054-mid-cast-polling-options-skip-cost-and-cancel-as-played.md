---
status: open
date: 2026-10-23
cards: Diana Iadanza; Scalpel Tongue
---

# ENG-054 - Mid-cast polling options skip cost and cancel-as-played

- Situation: `engine/politics.py::_cast_votes` applies a chosen mid-cast
  `POLLING_STEP` option with `option.apply` directly, not through
  `hooks.apply_chosen_option`. A `HookOption.cost` never runs, and no
  cancel-as-played window opens, so Diana Iadanza can never cancel a
  Scalpel Tongue played by the non-caller (offered only mid-cast, played
  as a Reaction). Both are in the Toreador suggested deck. Present since
  ENG-027; found by `rules-auditor` reviewing ENG-051. Today's mid-cast
  cards pay inside `apply`, so no cost is skipped yet.
- Sources read: Diana Iadanza (201694): "During a referendum she calls,
  Diana can burn 1 blood to cancel a reaction card as it is played (cost
  is still paid)." ENG-022 (cancel-as-played), ENG-050 (action modifier
  cost paid when played).
- Needed mechanism: route mid-cast choices through `apply_chosen_option`
  (cost, then cancel-as-played), keeping ENG-051's source pickup and
  ENG-027's cancellation on the returned id.
- Impacted code: `engine/politics.py::_cast_votes`; the stale notes in
  `cards/diana_iadanza.py` and `engine/hooks.py::mark_reaction_played`.
