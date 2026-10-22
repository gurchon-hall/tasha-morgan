---
status: resolved
date: 2026-10-18
cards: Aniel
---

# ENG-042 - Aniel - no per-attachment discipline-requirement marker

- Situation: Aniel (krcg id 201666): "Independent: Aniel can burn 1
  corruption counter or a card requiring a Discipline from another ready
  minion as a +1 stealth Ⓓ action that costs 1 blood." This entry's own
  first landing wrongly assumed the corruption-counter half was already
  fully supported generically via `engine/cards.py::CardAttachment.
  counters` -- that assumption was itself incorrect (see ENG-043) and is
  struck from this record rather than left to mislead a future reader; the
  "a card requiring a Discipline" half (this entry's actual scope) had no
  way to tell, from an arbitrary `CardAttachment` already in play, whether
  its own originating library card carries a nonzero printed Discipline
  requirement -- `CardAttachment` had no such field.
- Rules & interactions: a missing engine primitive, not a ruling ambiguity.
  Re-verified against each of the 5 already-implemented attaching cards'
  own krcg snapshots (Celerity 100312, Fame 100698, Perfectionist 101388,
  Pulled Fangs 101515, Weighted Walking Stick 102169): all 5 print an empty
  `discipline_requirement.disciplines`, so the new field correctly defaults
  `False` for every one of them without any further change to those
  modules. (Whether "a card requiring a Discipline" should also reach the
  "Discipline" master-card subtype itself is a secondary reading question,
  left open for whenever a card actually needs it -- no implemented card
  does.)
- Solution: `CardAttachment.requires_discipline` (`engine/cards.py`), set
  by the attaching card module at construction time, mirroring
  `is_equipment`'s own precedent; threaded through `engine/attachments.py::
  attach_card`'s own `requires_discipline` keyword. The
  discipline-requiring-card clause burns the whole attachment (`zone =
  "burned"`, left in the host's list, mirroring `resolve_one_attachment_
  contest`'s own convention). Per the Rulebook §8 glossary "Directed
  Action" entry ("targets one or more other Methuselahs, or the minions or
  cards they control"), the printed Ⓓ marker itself settles that "another
  ready minion" is the *opponent's* ready vampire only, not the acting
  Methuselah's own other vampires -- no separate RUL entry needed for
  that scoping. Aniel (201666) is `Status.IMPLEMENTED` (`src/vtesbot/
  cards/aniel.py`); its corruption-counter clause was fixed separately
  under ENG-043, against the primitive built there.
