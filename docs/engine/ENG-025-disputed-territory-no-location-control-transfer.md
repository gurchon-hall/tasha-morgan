---
status: resolved
date: 2026-10-14
cards: Disputed Territory
---

# ENG-025 - Disputed Territory - no location control-transfer

- Situation: Disputed Territory (krcg id 100557, Political Action):
  "Choose a location and a Methuselah. Successful referendum means the
  chosen Methuselah takes control of the chosen location." Needed a
  generic way to change who controls an existing in-play "location" — a
  concept ENG-015 already found is not a distinct krcg type, but free text
  on either a standalone Master card or an attached Equipment.
- Rules & interactions: rulings on file via krcg, verbatim: "If used to
  steal an equipment representing a location, it can be placed on any
  minion controlled by the new controller" [RTR 19960112]; "Changing the
  controller of a location has no other effect, unless specified by card
  text. Exception: A location 'on' another controlled card is moved onto
  an appropriate card controlled by the new controller of the location"
  [RTR 19980623]; "If used to 'change' the control of a location... to
  the same Methuselah, the location cannot be moved to another minion
  controlled by the same Methuselah" [LSJ 19971002].
- Solution: added `engine/attachments.py::transfer_attachment_control`
  (always re-hosts onto a caller-supplied destination vampire, per the
  Exception clause — an attached card is always "on" a vampire; rejects
  a same-controller call whose `new_host` is not the attachment's own
  current host, per [LSJ 19971002] — a `rules-auditor` finding fixed
  after this entry's first landing omitted that clause entirely) and
  `engine/master_cards.py::transfer_master_card_control` (never re-hosts a
  standalone card, only moves it between `PlayerState.master_cards` dicts
  and reassigns `controller`). Which destination vampire/controller to use
  is left to whichever future card module calls these (its own `Decision`,
  not built here). Disputed Territory's own card module (`cards/
  disputed_territory.py`, `Status.IMPLEMENTED`) was written in a later
  pass.
