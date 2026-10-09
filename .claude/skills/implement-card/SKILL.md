---
name: implement-card
description: Step-by-step workflow to implement one VtES card from the 2P allowed list — fetch official text and rulings, model the effect with engine hooks, write tests, register it. Use whenever a card is added or fixed.
---

# Implementing a card

## 1. Check legality
Look the card up in the active list `data/formats/2p/<date>.json`. Not listed → stop and report. Already implemented → you are fixing it; start from its tests.

## 2. Fetch the official data (never from memory)
Use KRCG. The README shows this usage; confirm it against the installed version (`python -c "import krcg; help(krcg.vtes)"`) before relying on any other attribute:
```python
from krcg.vtes import VTES

VTES.load()
card = VTES["Card Name"]
data = card.to_json()  # inspect keys: text, rulings, types, disciplines, costs…
```
Save the raw JSON to `data/cards/<card_id>.json` so the implementation is tied to a fixed text. If KRCG and the VEKN site disagree, report it.

## 3. Analyse the text
Write a short breakdown in the module docstring:
- verbatim card text (basic and superior levels separately);
- every ruling, verbatim, with its reference;
- card type(s), requirements (clan, discipline, capacity, title, sect), costs (blood / pool / other);
- timing window (master phase, out-of-turn, action, action modifier, reaction, combat step, unlock phase, "as played"…);
- target(s), duration ("for the remainder of combat", "this action", "until…").

Flag any wording referring to **prey / predator / "other Methuselahs" / votes from several players** — check it against the duel setting. Unclear → Open Question (see `vtes-rules-reference`), mark `blocked`.

## 4. Implement
- File: `src/vtesbot/cards/<snake_case_name>.py`.
- Use only hooks the engine exposes. Missing hook → stop, describe it, hand off to `rules-engineer`.
- Requirements and costs are checked by the card's `is_playable(observation-side context)` and surfaced as legal choices; never let an agent play an unplayable card.
- Superior/basic are separate choices when the vampire has the superior level.

## 5. Test
File: `tests/cards/test_<snake_case_name>.py`. Minimum:
- playable / not playable (requirements, costs, timing);
- each clause of the text, each discipline level;
- each ruling;
- interaction with being cancelled, if relevant;
- 2P-specific behaviour, if any.
Use the `rules-scenario-test` skill helpers.

## 6. Register
Add the entry to the card registry with `status = "implemented" | "blocked"`, the KRCG id, and the data snapshot path.

## 7. Report
One line per card: `Card Name — implemented (n tests)` or `Card Name — blocked: OQ-<n> / missing hook <x>`.
