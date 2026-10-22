---
status: resolved
date: 2026-10-08
cards:
---

# RUL-001 - Prey/predator duel wording

- Situation: with two players, each Methuselah is the other's prey
  and predator (Rulebook §5). Some card texts distinguish prey from
  predator, or refer to "other Methuselahs" in a way written for
  4-5 players.
- Rules & interactions: Rulebook §5's own worked example states
  verbatim, "each is prey of the other" — which by reciprocity (X is
  Y's predator iff Y is X's prey) also makes each the other's
  predator; the 2P variant's own exception list does not override
  this.
- Solution: confirmed as a rulebook fact, not an inference — with
  exactly two Methuselahs the sole opponent is simultaneously prey and
  predator. No card or engine path found so far needs to distinguish
  the two (every case collapses to "the opponent"); several modules
  (`engine/action.py`, `engine/ousting.py`, `cards/fleetness.py`,
  `cards/enchant_kindred.py`, `cards/line_brawl.py`,
  `cards/kine_resources_contested.py`) already cite this. A future
  card whose text assigns genuinely different effects to prey vs.
  predator specifically would need its own new RUL entry, not a reopening of
  this one.
