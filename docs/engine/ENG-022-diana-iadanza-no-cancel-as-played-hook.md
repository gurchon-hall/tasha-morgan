---
status: resolved
date: 2026-10-13
cards: Diana Iadanza
---

# ENG-022 - Diana Iadanza - no "cancel as played" hook

- Situation: Diana Iadanza (201694): "During a referendum she calls,
  Diana can burn 1 blood to cancel a reaction card as it is played
  (cost is still paid). +1 bleed." Found implementing this card (the
  "+1 bleed" clause needed no new engine work and is implemented
  separately): `Hook.CANCEL_AS_PLAYED` was named for classification
  only, with no dispatch call site anywhere — every Reaction card
  implemented so far resolves its entire effect atomically inside one
  `HookOption.apply()`, with no "announced, not yet resolved" moment
  for a third party to inject a cancellation.
- Rules & interactions: generic rulings on file for "cancel a card as it
  is played" ([LSJ 20061207]/[RBK playing-a-card]/[LSJ 20061013],
  [LSJ 20080630]/[LSJ 20011023], [ANK 20190104]/[RBK cancel-a-card]/
  [LSJ 19980212], [LSJ 20030224], [LSJ 20060106]) already fully
  specify the mechanic: played immediately, no other effects
  interleave; cost still paid; a "do not replace until" clause is also
  canceled; the card still counts as played (same-reaction-once-per-
  action still applies); a canceled limited effect does not trigger
  its own limit.
- Solution: a missing engine primitive, not an unsettled ruling. Added
  `engine/hooks.py::apply_chosen_option(state, option, played_by,
  may_cancel, context)`, sitting between "a `HookOption` is chosen"
  and "its effect runs," for both generic decision-loop helpers
  (`offer_until_pass`, `resolve_impulse_window`). `HookOption` gained
  an optional `cost` callable (runs unconditionally before any
  cancellation offer, keeping "cost is still paid" true even when the
  effect itself is suppressed); after `cost` runs, the *other* side is
  offered `CANCEL_AS_PLAYED_HOOK` once; choosing a cancellation runs
  its own `apply` and suppresses the original entirely.
  Zero-behaviour-change with no provider registered. A `rules-auditor`
  follow-up found and fixed a live landmine: Telepathic Counter's own
  `apply` atomically combined its cost (play-from-hand, §8 "used"
  bookkeeping) with its actual effect — split into `cost`/`apply` so a
  future cancellation can't also undo the card having been played.
  Organized Resistance/Protection Racket have the same atomic pattern
  but aren't yet exposed to `apply_chosen_option` — flagged for
  whoever wires their dispatch sites through it next. Diana Iadanza's
  own card module is not written for clause 1 — stays
  `blocked`/`ENG-022`; her "+1 bleed" clause is implemented separately.
