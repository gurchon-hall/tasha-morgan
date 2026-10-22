---
status: resolved
date: 2026-10-16
cards: Propaganda
---

# RUL-015 - Propaganda - who chooses which vampire to lock

- Situation: Propaganda's (krcg 101495) superior clause reads "...the
  target Methuselah locks a ready unlocked minion they control." No
  on-file ruling (for Propaganda, or for the structurally similar
  Brujah Debate/Sowing Dissension) settles whether the affected
  (target) Methuselah or the acting Methuselah chooses which qualifying
  vampire is locked, when there is no tie to break.
- Rules & interactions: live krcg text confirms the grammatical pattern
  ("[that Methuselah] locks a [vampire] they control") but Brujah
  Debate's own on-file ruling ([LSJ 19980224]) only resolves a
  tie-break among several vampires all "the oldest Brujah" -- not a
  general "sentence subject chooses" default. No general VEKN default
  for an unnamed decision-maker was found live.
- Solution (user ruling): Reading A -- the target (affected) Methuselah
  chooses, matching `engine/action.py::force_lock_ready_unlocked_
  minion`'s existing default. No code change needed.
  `cards/propaganda.py`'s superior clause may be wired to it as-is.
