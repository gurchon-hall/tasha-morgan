---
name: trim-comments
description: >-
  QA pass that audits code comments/docstrings (src/vtesbot) and the
  tracked rules docs (docs/OPEN_QUESTIONS.md, docs/DECISIONS.md,
  docs/open_questions_archive/) for content that no longer earns its
  place, per CLAUDE.md §6's "minimal comments, WHY only" rule and the
  OPEN_QUESTIONS.md cap/format in §2. Always run this before the
  closing-verification `pymarkdownlnt` pass (`uv run pymarkdown scan
  docs/ CLAUDE.md`) whenever a change touched a tracked `.md` file or
  added/edited comments -- trimming content first means markdownlint
  isn't reflowing prose that is about to be cut anyway. Use it whenever
  the user asks to "trim comments," "clean up docstrings," "tidy
  OPEN_QUESTIONS," or as part of closing out any card/engine/docs
  change.
---

# Trim comments and docs

A content audit, not a formatter. `ruff format` and `pymarkdownlnt`
already own whitespace, line length and Markdown structure -- this
skill's only question is whether a given sentence is still earning
its place. Never fight the formatters: if a comment or doc entry
needs rewording, write it so it already matches the project's prose
style and let `ruff`/`pymarkdown` do the rest.

Run it after other edits are otherwise done and before the closing
`pytest` / `ruff` / `pymarkdown` sequence (CLAUDE.md §6), so the
formatters run once, over final content, instead of twice.

## 1. Scan for candidates

```bash
python scripts/scan_comments.py
```

With no arguments this scans `src/vtesbot/engine`,
`src/vtesbot/cards` and `docs/OPEN_QUESTIONS.md`; pass paths to
narrow it to what the current change actually touched. It flags:

- inline comments that likely just restate the line they sit on;
- comments/docstrings written as task notes ("fix for...", "added
  for this PR", "see issue #123") instead of timeless rationale;
- a card module (`src/vtesbot/cards/<name>.py`) whose module
  docstring has no rule-source citation at all;
- `docs/OPEN_QUESTIONS.md` going over its 25-entry cap, and any
  `resolved` entry whose bullet labels aren't exactly Situation /
  Rules/interactions / Solution.

Exit code is 1 only for the entry-cap breach (an objective count);
everything else is a non-zero-information candidate list, not a
verdict. **A clean run does not mean the pass is done** -- the
script cannot tell a justified long docstring from padding, so most
of this skill's work is reading, not running the scanner. See the
script's own module docstring for exactly why each check is scoped
the way it is (in particular, why it does *not* check every
function/class docstring in `engine/` for a citation -- that
produces mostly noise, since most of those are plumbing, not rule
implementations).

## 2. Code comments and docstrings (src/vtesbot/)

The rule is CLAUDE.md §6, verbatim: *"Comments: minimal. Only when
the WHY is non-obvious (a rule subtlety, a workaround, an invariant);
never restate what the code already says. Docstrings still cite rule
sources (§2) and cover ruling-driven edge cases a reader couldn't
infer from the code."*

"Minimal" does not mean "short." The established house style for a
rule-implementing module (see any file in `src/vtesbot/cards/` or
the module docstrings in `src/vtesbot/engine/action.py`,
`hooks.py`, `turn_cards.py`) is a *long* docstring: verbatim card
text, verbatim rulings with their citation codes, the OQ(s) that
settled an ambiguity, and the engine-wiring rationale. That density
is the point -- every sentence in it answers a "why would the code
do it this way" question a reader would otherwise have to go dig up
from KRCG, the rulebook or `docs/OPEN_QUESTIONS.md` themselves. Do
not shorten these just to shorten them.

What actually gets trimmed:

- **Restatement.** `# increment the counter` above `counter += 1`.
  If removing the comment loses no information a competent reader
  wouldn't already have from the code, delete it.
- **Task/caller framing instead of timeless rationale.** A comment
  that only makes sense with the current PR/issue/conversation in
  hand ("added for the bleed fix", "per Martin's request", "handles
  the case from issue #123") should either be rewritten as the
  durable reason (what invariant or edge case it protects) or
  deleted if there isn't one -- that framing belongs in the commit
  message, not the file (see the top-level comment convention this
  project already follows).
- **Stale comments.** Cross-check a flagged or suspicious comment
  against the code it describes (`git log -p` / `git blame` on that
  hunk if the mismatch isn't obvious) -- a comment describing
  behavior the code no longer has is worse than no comment.
- **Missing required citation.** A card module's docstring must cite
  card text + rulings (the registered convention); an engine
  function implementing a specific rule (not plumbing) should cite
  its Rulebook/2P-variant section. If you can't find the citation it
  needs, that's a sign the rule was never sourced in the first place
  -- raise it as an Open Question (`vtes-rules-reference` skill)
  rather than inventing one. **Never write a citation you have not
  verified against the source** (CLAUDE.md §2's no-guessing rule
  applies to documentation exactly as much as to engine behavior).

When trimming a docstring that documents an implemented card or
rule, re-read it next to the actual card text / ruling / rule
section first -- don't cut a sentence just because it looks verbose
if it's covering a ruling-driven edge case a reader couldn't infer
from the code.

## 3. docs/OPEN_QUESTIONS.md

Procedure and cap live in CLAUDE.md §2 and `docs/DECISIONS.md` D-6;
this skill enforces the content side of it, not the mechanics of
archiving (that's `vtes-rules-reference`'s job when actually moving
entries). What to check here:

- Every `resolved` entry is trimmed to exactly three fields, in
  order: `Situation`, `Rules/interactions`, `Solution` (a label may
  carry a parenthetical qualifier, e.g. `Solution (user ruling, same
  precedent as OQ-20):` -- that's fine, the label itself must still
  be one of the three). This is the format commit `3a7cd98` settled
  on; don't invent a different shape for a new entry even if the
  old one being replaced used more fields.
- Entry count against the 25-entry cap. If adding a new entry would
  push the file over, archive the oldest `resolved` entries per
  CLAUDE.md §2 before adding the new one -- never trim an `open`
  entry just to make room; `open` entries are never archived
  regardless of age.
- Title convention: card-first where one exists -- `OQ-N` then the
  card name, then a short description, then the status -- per the
  same commit.
- A `resolved` entry's `Solution` should name *where* the fix lives
  (module/function) so a future reader doesn't have to re-derive it,
  but should not re-explain code that file's own docstring already
  covers in depth -- point at it instead of duplicating it.

## 4. docs/DECISIONS.md and docs/open_questions_archive/

- `DECISIONS.md` entries (`## D-N`) follow the existing
  Context/Decision/Consequence shape (some entries add Rationale) --
  keep a trimmed entry terse but don't force it into
  OPEN_QUESTIONS.md's stricter three-field shape; the two files
  document different things (architecture choices that stay true
  going forward vs. resolved rules ambiguities) and have always had
  separate formats.
- `open_questions_archive/<NNN>.md` is append-only once a file is
  full (CLAUDE.md §2) -- never re-trim an already-archived entry's
  content, and if `INDEX.md` and an archive file's actual entries
  ever disagree on which `OQ-N` lives where, fix `INDEX.md` to match
  the archive file (the archive file is the source of truth for
  content, the index is just a lookup aid).

## 5. Close out

After trimming, run the project's own closing-verification sequence
(CLAUDE.md §6) once, over the final content:

```bash
uv run pytest
uv run ruff check .
uv run pymarkdown scan docs/ CLAUDE.md
```

If a `data/` JSON file was touched in the process (it shouldn't be,
for this skill, but double-check), also run the `pretty-format-json`
check from CLAUDE.md §6.
