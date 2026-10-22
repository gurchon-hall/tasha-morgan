---
status: resolved
date: 2026-10-14
cards: On the Qui Vive
---

# ENG-030 - On the Qui Vive - no wake-before-candidates hook

- Situation: ENG-028's own `VampireInPlay.woken`/`clear_woken_vampires`/
  `AllyInPlay.skip_next_unlock` primitives let `is_ready_unlocked` honor a
  woken locked vampire everywhere it is already consulted (the block
  candidate list, every existing reaction-card provider's own eligibility
  check), but nothing in the engine ever offered a *defender*-side option to
  set `woken = True` on one of their own locked vampires *before*
  `engine/action.py::attempt_block`'s own candidate list
  (`state.ready_unlocked_vampires(defender)`) is computed each time around
  its retry loop -- the moment that matters for this card's primary
  "attempting to block" clause. The acting side had exactly this shape
  already (`INTERCEPT_DECREASE_HOOK`/`STEALTH_INCREASE_HOOK`, offered to
  `actor` via `hooks.offer_until_pass` at the very top of that same loop,
  before any candidate exists or is recomputed, ENG-021/RUL-011) -- no symmetric
  offer to `defender` existed anywhere in that function, or in any other
  hook dispatched before a block candidate is fixed.
- Rules & interactions: a missing engine primitive, not a ruling question
  (same category as ENG-028's own "engine-internal design choices, not ruling
  questions"); `BLOCK_CANDIDATE_INJECTION_HOOK` (ENG-018) was considered and
  rejected as the vehicle instead, since `attempt_block` always treats a
  chosen option from it as an *unconditional* successful block ("never runs
  the stealth/intercept ping-pong for this candidate"), contradicting this
  card's own block attempt (fully subject to normal stealth/intercept
  resolution, per [TOM 19951129] "the minion need not attempt to block...
  that is merely an option").
- Solution: added `WAKE_LOCKED_MINION_HOOK` (`cards/registry.py::
  Hook.WAKE_LOCKED_MINION`), offered to `defender` via `hooks.offer_until_
  pass` at the top of `attempt_block`'s retry loop, immediately after the
  two acting-side hooks' own offers there (actor's own proactive
  opportunities keep going first, Rulebook §2 Sequencing / CLAUDE.md rule
  4's "acting Methuselah gets the impulse first") and strictly before
  `candidates = state.ready_unlocked_vampires(defender)` is (re)computed,
  so a chosen option's own `apply` setting `woken = True` is picked up by
  that very computation, every time around the loop including on a retry
  (ENG-005). Same "no return value needed, `apply` just mutates state"
  contract as its two siblings. A provider waking an *ally* instead sets
  `AllyInPlay.skip_next_unlock = True` (ENG-028's own field, reused, not
  duplicated) -- allies are never themselves offered as block candidates in
  this engine (out of scope, ENG-028's own solution note), so that branch of
  the contract matters for a future ally-side use of this same hook, not for
  `attempt_block` itself. On the Qui Vive's own card module is not written;
  the primitive is complete.
