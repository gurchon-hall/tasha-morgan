---
status: open
date: 2026-10-23
cards: On the Qui Vive; Eyes of Argus
---

# ENG-060 - Wake cards - only offered before a block attempt

- Situation: On the Qui Vive and Eyes of Argus [AUS] are offered only
  through `WAKE_LOCKED_MINION`, before each block attempt (ENG-030). Their
  rulings allow more windows that the engine never offers. Found while
  migrating both modules to the `Card` API (step 6); the gap was recorded
  only in their old module docstrings.
- Sources read: [LSJ 20091123] "Can be played or used after action
  resolution (e.g. to use a reaction card like {Fast Reaction} after
  combat)." [ANK 20210817] "Can be played or used during the 'as a card is
  played' window, except in combat, or when there is no action."
  [TOM 19951129] the woken minion need not block or react.
- Needed mechanism: a wake window after action resolution and in the "as
  a card is played" window, plus a reaction window outside any action.
  No reaction card in the pool can be played in those windows today, so
  waking there would gain nothing; it matters once one is added (e.g.
  Fast Reaction).
- Impacted code: `cards/on_the_qui_vive.py`, `cards/eyes_of_argus.py`,
  `engine/action.py`.
