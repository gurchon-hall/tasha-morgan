---
status: resolved
date: 2026-10-17
cards: Precognition
---

# ENG-040 - Precognition - no round-1-only combat grant from block

- Situation: Precognition (krcg id 101475, Reaction, Mono Auspex):
  "[aus] +1 intercept. [AUS] As above, and this vampire can prevent 1
  damage during the first round of the resulting combat if they
  block." The superior clause's damage-prevention half needed two
  things no hook surface exposed: (1) a way for that reaction's own
  `apply()` (run during the block attempt's stealth/intercept
  resolution, before `run_combat` is even called) to hand a grant
  forward into the *later, separate* `run_combat` call for that same
  blocker; and (2) a way for a `DAMAGE_PREVENTION_HOOK` provider to
  tell "is this round 1 of the current combat."
- Rules & interactions: "The damage prevention can only be used if the
  block is successful, and only in the resulting (block-induced)
  combat." [LSJ 20010813]; "does not carry over to a follow-up combat"
  [LSJ 20010819-2]; "is provided again if a second block happens on
  the same action" [LSJ 20010814-2] — together read as a one-shot
  grant, tied to the specific vampire that played the card and that
  same vampire ending up as the blocker, usable at most once, only in
  round 1 of the one resulting combat.
- Solution: `engine/action.py::grant_block_time_combat_effect` records
  a grant into the block attempt's own `pending[PENDING_BLOCK_TIME_
  COMBAT_GRANT_KEY]`, keyed by the reacting vampire's instance id;
  `perform_minion_action` forwards only the entry keyed by the
  eventual successful `blocker` into that one `run_combat` call's
  `initial_combat_state` (`engine/combat.py::seed_block_time_combat_
  grants`/`block_time_combat_grant_available`/`consume_block_time_
  combat_grant`, keyed `BLOCK_TIME_COMBAT_GRANT_KEY`) — a grant for
  any other candidate is simply never read, and nothing carries into a
  second `run_combat` call. `engine/damage.py::is_round_one` reads a
  new `ROUND_NUMBER_KEY` that `run_combat` now writes into `round_
  state` at the top of each round, and `apply_damage` now also threads
  `combat_state` into `DAMAGE_PREVENTION_HOOK`'s own context alongside
  `round_state`. Generic mechanism proven in `tests/rules/test_block_
  time_combat_grant.py`; Precognition itself is now `Status.IMPLEMENTED`
  (`src/vtesbot/cards/precognition.py`, tests in `tests/cards/
  test_precognition.py`).
