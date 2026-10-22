---
status: resolved
date: 2026-10-18
cards: Seraphina
---

# ENG-041 - Seraphina - no ally starting-life tracking

- Situation: Seraphina (krcg id 201686): "Independent: Seraphina can add 2
  blood or life to a minion you control as a +1 stealth action, not to
  exceed starting life." The blood-to-vampire half was fully supported
  (`engine/damage.py::add_blood` already caps at effective capacity); the
  life-to-ally half needed to cap added life at that specific ally's own
  *printed* starting life, but `engine/state.py::AllyInPlay` carried only
  a live, damage-reducible `life` counter, with no separate record of the
  value it started at, and the engine had no `add_life` helper at all.
- Rules & interactions: a missing engine primitive, not a ruling ambiguity
  -- no rulebook/ruling source bears on the engine shape.
- Solution: `AllyInPlay.starting_life` (`engine/state.py`), fixed once by
  `engine/allies.py::recruit_ally` from the `life` it is already given at
  recruitment, mirroring a vampire's own `CryptCard.capacity` being fixed
  at print; `engine/allies.py::add_life`, a capped helper mirroring
  `add_blood`'s own `min(amount, cap - current)` shape. Seraphina (201686)
  is now `Status.IMPLEMENTED` (`src/vtesbot/cards/seraphina.py`), wired
  against `engine/phases/minion.py::ACTION_CARD_PLAY_HOOK` the same way
  Sakhar's own printed ability is (one option per eligible vampire/ally
  target, add deferred to `resolve()` so a blocked attempt adds nothing).
