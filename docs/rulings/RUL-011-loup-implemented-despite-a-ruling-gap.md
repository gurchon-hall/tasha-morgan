---
status: resolved
date: 2026-10-14
cards: Loup
---

# RUL-011 - Loup - implemented despite a ruling gap

- Situation: Loup's on-file ruling says "Can be used even if the stealth
  is not currently needed" [LSJ 20011214-2], but `cards/loup.py`'s own
  `STEALTH_MODIFIER_HOOK` provider could only ever be offered from inside
  `_duel_stealth_intercept`'s reactive "only when needed" ping-pong
  (`engine/action.py`) — so Loup could not be played against an
  unblockable action, or when no block is attempted at all, contrary to
  that ruling. The module shipped `Status.IMPLEMENTED` with the gap noted
  only in prose/a test name.
- Rules & interactions: krcg's on-file ruling for Loup (as above); this
  project's own ENG-021/RUL-009 precedent, where an identical shape (Perfect
  Paragon family needing to add a modifier outside the reactive-only
  window) was resolved by building a new proactive engine primitive
  (`INTERCEPT_DECREASE_HOOK`) rather than guessing around the gap.
- Solution (user-directed, Reading B): a new `STEALTH_INCREASE_HOOK`
  (`engine/action.py`), `INTERCEPT_DECREASE_HOOK`'s sibling for the acting
  side's own stealth -- offered proactively via `hooks.offer_until_pass` at
  the very top of `attempt_block`'s retry loop (alongside the existing
  `INTERCEPT_DECREASE_HOOK` own offer there) and reactively, merged into
  `_duel_stealth_intercept`'s existing union (`_ask_stealth_or_decrease`
  renamed `_ask_stealth_or_modifier`, now a three-way merge). Simpler than
  `ActiveInterceptDecrease`: a stealth increase is never candidate-
  dependent (intercept decrease's own `qualifies(blocker)` predicate exists
  only because intercept is a per-blocker value; stealth is a per-action
  value), so `ActiveStealthIncrease` needs only a `delta`, summed
  unconditionally into `_duel_stealth_intercept`'s `stealth` baseline the
  same way `_active_intercept_decrease` sums into `intercept` -- recomputed
  fresh every call, never cached, same ENG-005 convention. `cards/loup.py`'s
  own provider moved from `STEALTH_MODIFIER_HOOK` to `STEALTH_INCREASE_
  HOOK`, gaining its own per-action `LOUP_STEALTH_GRANTED_KEY` cap in
  `pending` (now reachable from both offer points, unlike the old single
  reactive one) so the standing +1 is activated at most once per action --
  without it, the old reactive-only wiring could in principle have
  restacked the same flat bonus indefinitely within one action (never
  exercised by any registered test, but a latent risk the new cap closes as
  a side effect). Perfect Paragon itself needed no change: its own
  superior clause already uses the (also proactive+reactive) `INTERCEPT_
  DECREASE_HOOK` directly and has no analogous gap. `tests/rules/
  test_stealth_increase.py` proves the mechanism generically (mirroring
  `test_intercept_decrease.py`); `tests/cards/test_loup.py::
  test_can_be_played_proactively_even_when_the_action_is_unblockable`
  proves the fix against the real card.
