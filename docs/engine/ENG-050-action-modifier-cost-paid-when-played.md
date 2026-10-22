---
status: resolved
date: 2026-10-22
cards:
---

# ENG-050 - Action modifier cost paid when played, not on resolve

- Situation: a card module must know when a cost is paid relative to a
  block: only for the card performing the action, or for every card played
  during it. The engine side of this was documented inside the
  `vtes-rules-reference` skill, mixed in with the rules summary.
- Rules & interactions: Rulebook §4 Minion Phase, block resolution: "the
  action's cost, if any, is only paid if the action succeeds; the cost is
  not paid if the action is blocked. The costs of action modifiers and
  reaction cards are always paid when the cards are played, regardless of
  the success of the action."
- Solution: the card performing the action pays its printed cost only
  inside its unblocked `resolve()` branch. An action modifier or reaction
  puts its cost in `HookOption.cost`, which
  `engine/hooks.py::apply_chosen_option` runs unconditionally the moment
  the option is chosen (the same path cancel-as-played uses, ENG-022).
