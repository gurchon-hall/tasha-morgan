---
status: open
date: 2026-10-22
cards: Dawn Operation
---

# ENG-049 - Whole-combat damage conversion to aggravated

- Situation: Dawn Operation (100501, on the 2P list, not implemented):
  "[for] If this action is blocked, all damage inflicted on vampires during
  the resulting combat is aggravated." The engine has no way to convert
  damage for a whole combat: `engine/combat.py::hand_strike_damage` always
  returns normal damage and nothing hooks `apply_damage` by damage source.
  Found by `rules-auditor` reviewing ENG-048.
- Sources read: card text and rulings via krcg (100501): "Only applies to
  damage done in combat, not damage done after combat like Catatonic Fear"
  [LSJ 20020314] [PIB 20130319]; "Applies to environmental and retainer
  damage too" [PIB 20150603-1].
- Needed mechanism: a combat-scoped conversion applied where damage reaches
  a vampire during combat (all sources, not only strikes), likely a
  `combat_state` flag read by `apply_damage`, rather than a hand-strike
  property.
- Impacted code: `engine/combat.py`, `engine/damage.py::apply_damage`;
  Dawn Operation once implemented.
