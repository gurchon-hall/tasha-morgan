---
status: resolved
date: 2026-10-14
cards: Loup
---

# ENG-024 - Loup - no action-succeeded signal or turn card

- Situation: Loup (krcg id 102273, Action Modifier, Toreador): "Only one
  Loup can be played each turn. Put this card in play. Toreador get +1
  stealth. Burn this card at the end of the turn or after a Toreador
  performs a successful action." Needed two missing primitives: a generic
  "this action just succeeded" signal (independent of whether the
  action's own effect did anything), and a "stays in play for the rest of
  the turn, until burned" entity distinct from both `CardAttachment` and
  the cross-turn `MasterCardInPlay`.
- Rules & interactions: Rulebook §4 "Resolve the Action" (re-fetched live),
  verbatim: "An action is successful only if it is not blocked" / "If the
  action is successful (all block attempts were unsuccessful), then the
  cost of the action is paid and the effects of the successful action
  take place" — success is purely "not blocked." "The turn" in Loup's own
  burn clause is unambiguous: VTES turns are strictly sequential (never
  two in progress at once), and this card can only ever be played by its
  own controller's own acting Toreador vampire, so "the turn" and "the
  controller's own turn" coincide by construction — no further question
  needed on that sub-point.
- Solution: added `engine/action.py::ACTION_SUCCEEDED_HOOK`
  (`cards/registry.py::Hook.ACTION_SUCCEEDED`), dispatched via
  `hooks.run_effects` immediately after `perform_minion_action`'s own
  `resolve(pending)` call returns (never on the blocked branch), carrying
  `actor_player`/`vampire`/`action`. Added `engine/state.py::
  TurnCardInPlay`/`PlayerState.turn_cards` and `engine/turn_cards.py`
  (`bring_turn_card_into_play`/`burn_turn_card`/`active_turn_cards`/
  `clear_turn_cards_at_end_of_turn`, the last wired into `engine/phases/
  turn.py::play_turn` right before the turn flips). Loup's own card module
  (`cards/loup.py`, `Status.IMPLEMENTED`) was written in a later pass; see
  its own docstring for the "only one Loup per turn" cap and a
  self-documented timing gap against the "can be used even if the stealth
  is not currently needed" ruling.
