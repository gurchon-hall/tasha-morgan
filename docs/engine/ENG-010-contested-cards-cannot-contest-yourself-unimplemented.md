---
status: resolved
date: 2026-10-10
cards:
---

# ENG-010 - Contested Cards - "cannot contest yourself" unimplemented

- Situation: found by `rules-auditor` while reviewing ENG-004/ENG-008's ally
  contest-detection fix: all four contest-detection functions
  (`engine/contests.py::detect_contest_on_reveal`, `engine/allies.py::
  detect_contest_on_recruit`, `engine/master_cards.py::
  detect_contest_on_bring_into_play`, `engine/attachments.py::
  detect_contest_on_attach`) only ever checked the *opponent's*
  same-named instances for a collision, never the incoming card's own
  controller's existing same-named instances.
- Rules & interactions: Rulebook §4 Advanced Rules > Contested Cards caution
  box, quoted verbatim: "You cannot control more than one of the same
  unique card at a time, and you cannot voluntarily contest cards with
  yourself (if some effect would force you to contest a card with
  yourself, then you simply burn the incoming copy of the unique card)."
- Solution: each of the four functions now checks the incoming card's own
  controller's other live same-named instance first (same zone test as
  its existing opponent-side check); a same-controller collision burns
  the incoming copy immediately (`zone = "burned"`) and returns before
  ever reaching the opponent-side contest check, so no contest is created
  in that case.
