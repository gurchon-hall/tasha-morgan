---
status: resolved
date: 2026-10-18
cards: Sergio Bueno
---

# ENG-044 - Sergio Bueno - no block-attempt mandatory cost-gate hook

- Situation: Sergio Bueno (krcg 201662): "Minions with 1 or more of your
  corruption counters must burn 1 blood or life to attempt to block
  Sergio." Neither `block_candidate_predicate` (a stateless, per-action-
  card property filter) nor `BLOCK_CANDIDATE_EXCLUSION_HOOK` (an
  actor-chosen exclusion) fit: this is a passive crypt ability spanning
  every action type its vampire ever performs, and a mandatory cost paid
  the instant a candidate attempts, win or lose -- not merely a boolean
  filter.
- Rules & interactions: a missing engine primitive, not a ruling ambiguity
  (same category as ENG-028/ENG-030/ENG-039's own "missing/deferred engine capability"
  classification) -- the card text and its one on-file ruling
  ([LSJ 20011022], moot here since the engine never offers a torpid
  vampire as `acting_vampire` in the first place) already settle the rule.
- Solution: `engine/action.py::BlockAttemptCost`/`BLOCK_ATTEMPT_COST_HOOK`,
  dispatched per-candidate (both the hardcoded `ready_unlocked_vampires`
  list and `BLOCK_CANDIDATE_INJECTION_HOOK` options) via the new
  `engine/hooks.py::collect` combinator; a candidate that cannot afford an
  applicable cost is not offered at all, one that can pays it
  (`_pay_block_attempt_costs`) the instant it is chosen, before the
  stealth/intercept duel. Generic mechanism proven in `tests/rules/
  test_block_attempt_cost.py`; Sergio Bueno (201662) is now
  `Status.IMPLEMENTED` (`src/vtesbot/cards/sergio_bueno.py`, tests in
  `tests/cards/test_sergio_bueno.py`).
