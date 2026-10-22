---
name: card-pipeline
description: >-
  Main-session orchestration for taking one card (or a deck's missing
  cards) from "not implemented" to "ready for the user to commit":
  which agent runs when, what each one is given, and the checks between
  them. Use when the user asks to implement cards or to make a deck
  playable.
---

# Card pipeline (main session)

The agents each do one part; this is the loop that connects them.
Nothing here stages or commits (CLAUDE.md §6).

## 0. Pick the cards

For a deck: `uv run python scripts/deck_coverage.py` lists what is
missing and an order that unlocks the most. Take one card at a time,
unless several need no engine change.

## 1. Implement

Spawn `card-implementer` with the card name, krcg id and the active
list path. Do not pass guesses about the card's rules.

On return, run `git status` and compare it to the reported files.
Then branch on its report:

- `implemented` → step 3.
- `blocked: ENG-<nnn>` → step 2.
- `blocked: RUL-<nnn>` → show the user the entry's candidate readings
  and stop on that card until they rule.

## 2. Engine gap

Spawn `rules-engineer` with the `ENG` id (it follows
`add-engine-hook`). When it is done, spawn `card-implementer` again to
unblock the card. The engine change and the card are separate
proposed commits.

## 3. Audit

Spawn `rules-auditor` with the list of cards and mechanisms changed
and the scope to read (`git diff HEAD -- <files>` plus the new files).
Never pass the implementer's explanation: independence is the point.
Always audit engine changes; audit cards at least per batch.

- blocker / major → back to the agent that wrote the code (or a new
  `RUL`/`ENG` entry if it is a sources question), then re-audit
  that part;
- minor → fix it or list it for the user.

## 4. Trim and verify

Run the `trim-comments` pass on the touched files, then
`uv run python scripts/check.py`. Fix until green.

## 5. Hand over

For each proposed commit (one card or one mechanism): its files, a
message in the repo's style (`feat(cards): ...`, `feat(engine): ...
(ENG-<nnn>)`), the `check.py` summary, the audit outcome, and any
open `RUL`/`ENG` entry the user must decide.
