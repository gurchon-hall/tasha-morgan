---
status: resolved
date: 2026-10-09
cards:
---

# RUL-003 - Contested crypt card trigger moment

- Situation: the 2P contested-crypt-card rule gave the resolution cost
  (1 pool/unlock or yield) but not the precise moment a contest
  begins.
- Rules & interactions: 2P variant page, verbatim: "If more than one
  unique crypt card with the same name is brought into play, that
  means control of the card is being contested... A second copy
  brought in later is immediately contested, and can still be used as
  normal."
- Solution: confirms the contest triggers on reveal into play, not
  while both copies are merely face down/uncontrolled.
  `src/vtesbot/engine/contests.py::detect_contest_on_reveal` already
  implemented this correctly — no code change needed.
