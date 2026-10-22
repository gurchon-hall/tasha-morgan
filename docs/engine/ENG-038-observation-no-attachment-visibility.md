---
status: resolved
date: 2026-10-16
cards:
---

# ENG-038 - Observation - no attachment visibility

- Situation: `rules-auditor`, reviewing Pulled Fangs, found
  `engine/observation.py::VampireView` has no `attachments` field at
  all, while a played attachment card (Pulled Fangs, Perfectionist,
  Weighted Walking Stick) is also left sitting in `Observation.
  ash_heap` (`play_from_hand` appends there unconditionally; nothing
  removes it once the same physical card becomes a live
  `CardAttachment`).
- Rules & interactions: CLAUDE.md §5 (information-hiding invariant);
  Rulebook §3 "Playing a Card" ("showing the card") confirms an
  attachment is always public once played -- not a ruling question,
  a project observation-fidelity gap.
- Solution: added `engine/observation.py::AttachmentView`
  (`instance_id`/`krcg_id`/`name`/`controller`/`counters`/
  `is_equipment`, `zone == "attached"` only) and
  `VampireView.attachments`, gated behind the existing
  `visible_identity` check (defensive -- no attach path in this
  engine ever targets a face-down uncontrolled vampire today).
  `ash_heap` double-listing fixed by a count-based filter
  (`_live_attachment_counts_by_controller`/`_visible_ash_heap`): hides
  at most as many same-`krcg_id` `ash_heap` entries as there are
  currently-live attachments of that id. `rules-auditor` noted this is
  index-based, not identity-based (could in principle hide a different
  same-named copy's entry than the one that actually became the
  attachment), but confirmed harmless under `ash_heap`'s own
  name-only, display-only shape -- worth revisiting only if `ash_heap`
  ever gains instance-level fidelity.
