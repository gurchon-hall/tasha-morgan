---
status: resolved
date: 2026-10-11
cards: Fame
---

# ENG-014 - Fame - contested cards gap beyond crypt/ally

- Situation: Fame (100698, Unique master card attached via
  `CardAttachment`) has the same "two independently-built decks could
  both play a copy" exposure ENG-004 already fixed for allies, but
  `CardAttachment` had no contest tracking of its own at all.
- Rules & interactions: the same unified Contested Cards mechanism
  (ENG-004/ENG-009) applies unmodified to an attached Unique master card —
  the 2P crypt-card override does not reach it.
- Solution: `CardAttachment` gained `controller`/`instance_id`/`zone`/
  `contested_with` (no longer frozen); `engine/attachments.py::
  attach_card`/`detect_contest_on_attach`/
  `resolve_one_attachment_contest` mirror the ally-side functions;
  `unlock.py` extended with a `"contest_attachment:"` branch. A
  contest is tracked against the attachment's own *controller* (who
  played it), not the host vampire's controller — clarified in a
  follow-up addendum after a `rules-auditor` finding that the initial
  docstring overclaimed the Master-card controller rule as if it
  covered a future Equipment/Retainer attachment too (it doesn't —
  those follow the Minion-card controller rule instead; corrected by
  documentation only, no card uses this yet). Fame itself stays
  `blocked`.
