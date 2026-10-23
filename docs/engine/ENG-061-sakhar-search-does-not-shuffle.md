---
status: open
date: 2026-10-23
cards: Sakhar
---

# ENG-061 - Sakhar - library search does not shuffle

- Situation: Sakhar (201685) "can search your library for an equipment
  card, reveal it and move it to your hand as a +1 stealth action."
  `cards/sakhar.py` takes the named card out of the library and does not
  shuffle; its old docstring read the card's silence as "no shuffle".
  Found while migrating the module to the `Card` API (step 6).
- Sources read: Rulebook §3 Wording templates, "Search": "You do not have
  to announce the card you are searching, and searching can result in not
  finding the card. If you search your library or crypt, you must shuffle
  it afterwards." The card text is silent, so the rulebook applies.
- Needed mechanism: shuffle the library through `state.rng.shuffle` once
  the search resolves, found or not. The search should also be offered
  with no equipment in the library ("can result in not finding the card"),
  which still shuffles. Both change the RNG stream, so the fix gets its own
  commit and determinism run.
- Impacted code: `cards/sakhar.py`, `tests/cards/test_sakhar.py`.
