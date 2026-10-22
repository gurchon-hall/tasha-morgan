---
name: implement-card
description: >-
  Step-by-step workflow to implement one VtES card from the 2P allowed
  list — fetch official text and rulings, model the effect with
  engine hooks, write tests, register it. Use whenever a card is
  added or fixed.
---

# Implementing a card

## 1. Check legality

Look the card up in the active list `data/formats/2p/<date>.json`.
Not listed → stop and report. Already implemented → you are fixing
it; start from its tests.

## 2. Fetch the official data (never from memory)

Use KRCG. The API has changed across versions — confirm it against the
installed version (`python -c "import krcg; print(krcg.__version__)"`,
`help(krcg.load)`) before relying on any attribute name. As of krcg 4.18
(this project's installed version), there is no `krcg.vtes` submodule at
all (`from krcg.vtes import VTES` raises `ModuleNotFoundError`); use:

```python
import krcg

cards = krcg.load()
card = cards["Card Name"]  # or cards[krcg_id]
data = card.to_json()  # inspect keys: text, rulings, types, ...
```

Save the raw JSON to `data/cards/<card_id>.json` so the implementation
is tied to a fixed text. If KRCG and the VEKN site disagree, report
it.

## 3. Analyse the text

Write a short breakdown in the module docstring — short means it,
per CLAUDE.md §6 (minimal comments, WHY over WHAT): aim for under
~20-25 lines, not an essay on how you investigated it.

- verbatim card text (basic and superior levels separately) — this
  one is always quoted in full, it's the one thing memory must never
  stand in for;
- requirements (clan, discipline, capacity, title, sect), costs
  (blood / pool / other), timing window, target(s), duration;
- rulings: cite the reference for each one; quote the wording verbatim
  only when the exact phrasing is load-bearing for the implementation
  or the blocked/implemented decision — otherwise a one-line summary
  with its citation is enough, especially for rulings that are generic
  background and not specific to this card;
- state the WHY only where a reader couldn't infer it from the code:
  which clause is blocked and why, which engine hook it rides on. Do
  not restate this checklist, narrate alternatives you rejected, or
  re-explain a `RUL`/`ENG` entry already written up under `docs/` —
  cite it by id instead of repeating it.

Flag any wording referring to **prey / predator / "other
Methuselahs" / votes from several players** — check it against the
duel setting. Unclear → `RUL` entry (see `vtes-rules-reference`),
mark `blocked`.

## 4. Implement

- File: `src/vtesbot/cards/<snake_case_name>.py`.
- Use only hooks the engine exposes. Missing hook → stop, describe
  it, hand off to `rules-engineer`.
- Requirements and costs are checked by the card's
  `is_playable(observation-side context)` and surfaced as legal
  choices; never let an agent play an unplayable card.
- Superior/basic are separate choices when the vampire has the
  superior level.

## 5. Test

File: `tests/cards/test_<snake_case_name>.py`. Minimum:

- playable / not playable (requirements, costs, timing);
- each clause of the text, each discipline level;
- each ruling;
- interaction with being cancelled, if relevant;
- 2P-specific behaviour, if any.

Use the `rules-scenario-test` skill helpers.

## 6. Register

Add the entry to the card registry with
`status = "implemented" | "blocked"`, the KRCG id, and the data
snapshot path.

## 7. Report

One line per card: `Card Name — implemented (n tests)` or
`Card Name — blocked: RUL-<nnn> / ENG-<nnn> (missing hook <x>)`.
