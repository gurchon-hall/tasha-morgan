---
status: resolved
date: 2026-10-12
cards: Taste of Vitae
---

# ENG-020 - Taste of Vitae - no end-of-round window

- Situation: Taste of Vitae (101945, "only usable at the end of a
  round of combat... gains blood equal to the amount of blood lost by
  the opposing vampire to damage this round") needed two missing
  mechanisms: an End of Round hook/window (Rulebook §4 step 7), and a
  round-scoped "blood lost specifically to damage this round"
  accumulator (distinct from a vampire's raw blood deficit, which
  could reflect unrelated effects).
- Rules & interactions: rulings on file confirm it's playable after a
  round ends prematurely, before/after other end-of-round effects, and
  even if the opponent was burned (so the accumulator must stay
  readable after a burn).
- Solution: added `Hook.END_OF_ROUND`/`END_OF_ROUND_HOOK`, dispatched
  exactly once per round on every exit path via a restructured round
  loop (`still_ready`/`pressed` booleans replacing scattered
  `break`s), offered as a real two-sided repeatable impulse window
  (not a single binary ask like press). Added `BLOOD_LOST_TO_DAMAGE_
  KEY` inside `round_state`, written by `apply_damage`'s mend and
  aggravated-burn branches via `record_blood_lost_to_damage`, queried
  via `blood_lost_to_damage_this_round`. Taste of Vitae itself was
  then implemented against both (per-round per-vampire play cap,
  zone/hand gates, reading the opponent's own blood-loss record fresh
  at apply time). `Status.IMPLEMENTED`.
