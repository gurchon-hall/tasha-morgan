---
status: open
date: 2026-10-23
cards: Disputed Territory; Dominate Kine
---

# ENG-063 - Location targets limited to "Unique location." masters

- Situation: Disputed Territory (100557) "Choose a location ..." and
  Dominate Kine (100573) "[DOM] Ⓓ Steal a location." both use
  `cards/disputed_territory.py::LOCATION_KRCG_IDS`, built from 2P-list cards
  whose text starts with "Unique location.", and transfer only standalone
  master cards. A non-unique location ("Location.") and an equipment
  location attached to a vampire (e.g. Living Manse, 101114: "Location.
  While in play, this card does not count as equipment.") are never
  offered. No such card is on the active 2P list (2026-10-03), so no legal
  game reaches the gap today. Raised by the user, 2026-10-23.
- Sources read: Disputed Territory rulings: "Requirements do not apply
  when taking control of a card already in play." [TOM 19960226-1]; "If
  used to steal an equipment representing a location, it can be placed on
  any minion controlled by the new controller." [RTR 19960112]; same
  controller cannot move it [LSJ 19971002]. Living Manse: "May be put on
  any minion if the controller changes. If the new controller has no
  minions, it is burned." [RTR 19960112]. User ruling (2026-10-23): Living
  Manse attached to a vampire is a legal target; stealing it means choosing
  one of the new controller's vampires to carry it, regardless of
  restrictions.
- Needed mechanism: one shared "is a location" test (the card text's
  location marker, unique or not) instead of the "Unique location." id
  set; location attachments offered as targets beside standalone ones; on
  a control change, the new controller chooses a host among their
  vampires through `engine/attachments.py::transfer_attachment_control`
  (ENG-025), and the card burns if they control none. Rewilding (101632,
  "Burn a location", not implemented) would use the same test.
- Impacted code: `cards/disputed_territory.py`, `cards/dominate_kine.py`,
  their tests and the location sweep test. To land with ENG-062.
