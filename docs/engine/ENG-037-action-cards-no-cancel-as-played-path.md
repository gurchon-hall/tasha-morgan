---
status: resolved
date: 2026-10-16
cards:
---

# ENG-037 - Action cards - no cancel-as-played path

- Situation: `rules-auditor`, reviewing Propaganda/Dominate Kine,
  found `engine/phases/minion.py::_perform_action_card` called
  `option.apply(state)` directly, never through `engine/hooks.py::
  apply_chosen_option` -- so no Reflex-type card could ever cancel an
  Action card "as played." A first fix pass introduced two further
  problems a follow-up audit caught: (1) the replacement-card draw ran
  *before* the cancel window instead of after; (2) no generic "same
  named action card at most once per turn" cap existed anywhere,
  already live-violated by every implemented Action card (Dominate
  Kine, Propaganda, Fleetness, Enchant Kindred, Disputed Territory,
  Kine Resources Contested, Line Brawl, Parity Shift).
- Rules & interactions: Rulebook §2 Card Types, "Library Cards" Advanced
  Rules (`data/sources/rulebook/2026-10-09/2-card-types.md:124-126`):
  "Some effects can cancel a card 'as it is played.' ... Even drawing
  to replace cards, comes after this time period." §3 "Cancel a card"
  (`3-playing-the-game.md:103-108`): a cancelled card is still
  considered played; an action card's own minion does not lock and
  "they can play the same action card again." §4 Detailed Turn
  Sequence (`4-detailed-turn-sequence.md:188-191`): "A minion cannot
  play (unless cancelled) the same named action card more than once
  each turn, even if they unlock" -- scoped per-minion, not
  per-controller.
- Solution: `engine/hand.py::remove_from_hand`/`draw_replacement_card`
  split the physical-card-removal and replacement-draw steps;
  `_perform_action_card` now sequences `option.apply` -> cancel offer
  (`hooks.offer_cancel_as_played`) -> unconditional replacement draw
  -> (only if not canceled) mark the per-turn cap and run
  `perform_minion_action`. `VampireInPlay.action_card_played_turn`
  (name-keyed, per-minion, storing the turn last played) backs
  `action_card_already_played_this_turn`/
  `mark_action_card_played_this_turn`, checked by all 8 real
  `ACTION_CARD_PLAY_HOOK` providers. Loup (Action Modifier, not
  Action) and `lucinde_alastor.py` (never plays a card from hand) are
  both correctly out of scope, confirmed rather than assumed.
