---
status: resolved
date: 2026-10-10
cards: Celerity
---

# ENG-002 - Celerity - attachment effects unconsulted

- Situation: Celerity (100312, Discipline master card): "+1 level of
  Celerity [cel], +1 capacity. Cannot be put on a vampire with
  superior Celerity [CEL]." Attaching the card was already wired
  (`CardAttachment`, the `"master_phase_play"` hook); its two numeric
  effects had no consumer — every capacity/discipline-level read in
  the engine read `vampire.card.*` directly, bypassing
  `VampireInPlay.attachments`.
- Rules & interactions: plain printed text, no ruling ambiguity — the
  generic "Discipline"-type master-card pattern (one per discipline).
- Solution: added `engine/attachments.py::effective_capacity`/
  `effective_disciplines`, two new passive hooks
  (`"capacity_modifier"`, `"discipline_level_modifier"`); updated
  every `engine/` reader (`damage.py::add_blood`, both
  `phases/influence.py` capacity checks,
  `observation.py::VampireView.capacity`) to consult them instead.
  Celerity's own card module stays `blocked`; `threats.py`/
  `telepathic_counter.py` still read the raw field directly, flagged
  for a future pass.
