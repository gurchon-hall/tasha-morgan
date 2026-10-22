---
status: resolved
date: 2026-10-18
cards: Forced Confessional
---

# ENG-045 - Forced Confessional - no force-block-attempt-failure hook

- Situation: Forced Confessional (krcg 102250): "[DOM] That attempt fails
  and the blocking minion cannot attempt to block this action again." The
  "cannot attempt to block this action again" half fits the existing
  `BLOCK_CANDIDATE_EXCLUSION_HOOK`/`PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY`
  primitive directly (a provider may write to it from any hook's own
  `apply`, not only from that hook's own proactive offer point). "That
  attempt fails" does not: every existing acting-side tool at the reactive
  point a block attempt is already in progress
  (`INTERCEPT_DECREASE_HOOK`/`STEALTH_INCREASE_HOOK`,
  ENG-021/RUL-009/RUL-011) only ever
  adjusts the `stealth`/`intercept` numbers `_duel_stealth_intercept`
  compares, then loops back to let the defender respond again -- none
  terminates that comparison outright. An extreme decrease (e.g. -999)
  would still leave the defender free to add intercept back before the
  duel ends, which is not what "that attempt fails" (an unconditional,
  immediate result) means.
- Rules & interactions: a missing engine primitive, not a ruling ambiguity
  (same category as ENG-028/ENG-030/ENG-039/ENG-044's own
  classification) -- the card text
  has no on-file ruling (`rulings == []`) and needs none to settle the
  engine shape.
- Solution: added `FORCE_BLOCK_ATTEMPT_FAILURE_HOOK` (`cards/registry.py::
  Hook.FORCE_BLOCK_ATTEMPT_FAILURE`), offered alongside `INTERCEPT_DECREASE_
  HOOK`/`STEALTH_INCREASE_HOOK` in `_duel_stealth_intercept`'s own "block
  currently succeeds" branch, merged into the same `Decision` via
  `_ask_stealth_or_modifier`. Choosing it makes `_duel_stealth_intercept`
  return a new third value, `forced_failure=True`, read by `attempt_block`
  before it ever compares `intercept >= stealth` -- the attempt is treated
  as failed outright (loops back, same as any other failed attempt),
  independent of the numbers in play. Proven generically in `tests/rules/
  test_force_block_attempt_failure.py`. Forced Confessional (102250) is now
  `Status.IMPLEMENTED` (`src/vtesbot/cards/forced_confessional.py`,
  `Hook.FORCE_BLOCK_ATTEMPT_FAILURE`/`Hook.INTERCEPT_DECREASE`, tests in
  `tests/cards/test_forced_confessional.py`), its basic clause ("[dom] The
  blocking minion gets -1 intercept") wired against the pre-existing
  `INTERCEPT_DECREASE_HOOK` with a `qualifies` predicate scoped to the one
  specific blocking vampire fixed in context, not a property class (unlike
  Perfect Paragon's own "younger vampires"). Follow-up (`rules-auditor`
  finding on this entry's first landing): the hook was only offered in the
  "block currently succeeds" branch, so the exclusion half of the superior
  clause ("cannot attempt to block this action again") was never reachable
  while a candidate was already failing on the raw numbers -- a legal choice
  silently never offered (CLAUDE.md §5). "Only when needed" (RUL-009/RUL-011) scopes
  solely to stealth/intercept *value* modifiers; it does not scope this
  hook's own non-numeric exclusion half, which has nothing to do with the
  current numbers (Rulebook §4 "Resolve Any Block Attempts": a failed
  attempt may be retried "as often as the blocking Methuselah wishes").
  Fixed by also offering `FORCE_BLOCK_ATTEMPT_FAILURE_HOOK` to the actor,
  alone (not merged with any numeric modifier, since none are needed there),
  in the "block currently fails on the raw numbers" branch too, once the
  defender has declined or exhausted `INTERCEPT_MODIFIER_HOOK` -- impulse
  returning to the actor. Proven by `tests/rules/test_force_block_attempt_
  failure.py::test_offered_even_while_already_failing_on_the_raw_numbers`.
