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

## 2. Fetch and snapshot the official data (never from memory)

The project pins krcg ≥ 5.14 (`pyproject.toml`). `krcg.load()`
returns a `CardDict`; there is no `krcg.vtes` module and cards have
no `to_json()`. Check the installed version first (`uv run python -c
"import importlib.metadata as m; print(m.version('krcg'))"`) and
re-check attribute names with `dir(card)` if it changed.

```python
import krcg
import msgspec

card = krcg.load()["Card Name"]  # or [krcg_id]
card.text, card.rulings  # the clauses and rulings to cover
path = f"data/cards/{card.id}.json"
with open(path, "wb") as f:
    f.write(msgspec.json.format(msgspec.json.encode(card), indent=2))
```

Then run the data JSON fix from CLAUDE.md §6 on that file. The
snapshot ties the implementation to a fixed text; it is the verbatim
record, so the docstring does not repeat it. If KRCG and the VEKN
card page disagree, report it.

## 3. Analyse the text (in your head and the tests, not the docstring)

- requirements (clan, discipline, capacity, title, sect), costs
  (blood / pool / other), timing window, target(s), duration;
- each ruling and what it changes;
- wording referring to **prey / predator / "other Methuselahs" /
  votes from several players**: check it against the duel setting
  (RUL-001). Unclear → `RUL` entry (`vtes-rules-reference`), block
  the card.

## 4. Implement

- File: `src/vtesbot/cards/<snake_case_name>.py`, built on
  `cards/card.py::Card` (`cards/celerity.py` shows the API; its
  docstring predates the 3-line rule). Do not copy modules that still
  call `register(CardRegistration(...))`.
- Docstring, 3 lines max (CLAUDE.md §6):

  ```python
  """Celerity (Master: Discipline). krcg 100312. Snapshot: data/cards/100312.json
  Superior is read from effective disciplines, so copies stack (ENG-002)."""
  ```

- `card = Card(KRCG_ID, "Name", "<krcg type>")` registers the card;
  library cards need the type. Wire each effect with
  `@card.on(Hook.X)` on `def _name(state: GameState, ctx: XContext)`,
  `XContext` from `engine/hook_contexts.py`: its docstring is the
  hook's contract, and `Card.on` refuses any other annotation. Offer
  choices with `card.option(value, label, apply)` so the agent only
  ever sees legal plays. Requirements and
  costs are checked inside the provider: an unplayable card yields no
  option.
- Superior/basic are separate options when the vampire has the
  superior level.
- Missing hook → do not work around it. Open an `ENG` entry, call
  `card.block("ENG-<nnn>", planned_hooks=(...))` with no providers
  wired, and report it for `rules-engineer` (`add-engine-hook`).
- Unclear ruling → same, with `card.block("RUL-<nnn>")`.

## 5. Test

File: `tests/cards/test_<snake_case_name>.py`. Minimum:

- playable / not playable (requirements, costs, timing);
- each clause of the text, each discipline level;
- each ruling;
- interaction with being cancelled, if relevant;
- 2P-specific behaviour, if any.

Use the `rules-scenario-test` skill helpers.

## 6. Verify

`Card(...)` registers itself; there is no separate registry edit, and
`cards/__init__.py` loads every module. Add the module to
`[tool.basedpyright].include` in `pyproject.toml`. Run
`uv run python scripts/check.py`.

## 7. Report

One line per card: `Card Name — implemented (n tests)` or
`Card Name — blocked: RUL-<nnn> / ENG-<nnn> (missing hook <x>)`, plus
the file list and the `check.py` summary.
