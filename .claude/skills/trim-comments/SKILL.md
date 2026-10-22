---
name: trim-comments
description: >-
  Content pass over code comments/docstrings and the rules docs
  (docs/rulings/, docs/engine/, docs/design/): enforce CLAUDE.md §6's
  3-line cap and keep only the WHY, moving reasoning into RUL/ENG/DES
  entries. Run it on what a change touched, after the edits and before
  `scripts/check.py`. Use it whenever the user asks to trim comments,
  clean up docstrings or tidy the rules docs, and when closing out any
  card/engine/docs change.
---

# Trim comments and docs

A content audit, not a formatter: `ruff format` and `pymarkdownlnt`
own layout. The question here is whether each sentence earns its
place, and where it belongs if not in the code.

## 1. Scan what the change touched

```bash
uv run python scripts/comment_lines.py        # hard cap, changed lines
uv run python scripts/scan_comments.py <paths>  # candidates to read
```

`comment_lines.py` fails on any docstring or `#` block over 3 lines
that overlaps a changed line. `scan_comments.py` only lists
candidates (restatement, task framing, card modules with no citation,
resolved entries with the wrong labels); a clean run does not mean the
pass is done.

Scope is the current change. Legacy code over the cap is migrated in
its own planned pass (CLAUDE.md §10); do not trim untouched files on
the side.

## 2. Code (src/, tests/, scripts/)

The rule is CLAUDE.md §6: at most 3 lines per docstring and per `#`
block; only the non-obvious WHY; a docstring implementing a rule cites
its source.

What stays:

- the source citation (`Rulebook §4 Combat`, `2P variant §2.3`) and
  entry ids (`ENG-022`, `RUL-009`);
- the contract a caller needs (for a hook: dispatch style, who is
  asked, what a provider returns, an example card);
- an invariant or rule subtlety the code cannot show.

What goes:

- restatement of the code;
- task framing ("fix for...", "added for this PR", "per the user's
  request"): that belongs in the commit message;
- history, investigation narrative, rejected alternatives, quoted
  rulings, verbatim card text (the card snapshot holds it).

Before deleting a fact that is not already in an entry, move it to
the `RUL`/`ENG`/`DES` entry that owns it and cite the id. Never write
a citation you have not checked against the source (CLAUDE.md §2); a
rule with no findable source is a `RUL` entry candidate.

A card module's docstring is name, type, krcg id, snapshot path, and
at most one line of entry ids or non-obvious WHY:

```python
"""Celerity (Master: Discipline). krcg 100312. Snapshot: data/cards/100312.json
Superior is read from effective disciplines, so copies stack (ENG-002)."""
```

Check a suspicious comment against the code it describes (`git log
-p` / `git blame` on that hunk): a comment describing behaviour the
code no longer has is worse than none.

## 3. Rules docs (docs/rulings/, docs/engine/, docs/design/)

The entry format and the closing trim are defined once, in the
`vtes-rules-reference` skill ("Procedure" and "Closing an entry").
Check against it:

- a `resolved` RUL/ENG entry has exactly `Situation` / `Rules &
  interactions` / `Solution` (a parenthetical qualifier on a label is
  fine);
- a DES entry has `Context` / `Decision` / `Consequence`; a
  superseded one is a short stub with `superseded_by`;
- the title and front matter match the entry's real state;
- `Solution` names where the fix lives, without re-explaining code.

Regenerate the index after any title or front-matter edit: `uv run
python scripts/docs_index.py`.

## 4. Close out

Run `uv run python scripts/check.py` once, over the final content.
