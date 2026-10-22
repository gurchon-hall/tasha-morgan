---
name: trim-comments
description: >-
  QA pass that audits code comments/docstrings (src/vtesbot) and the
  tracked rules docs (docs/rulings/, docs/engine/, docs/design/) for
  content that no longer earns its place, per CLAUDE.md §6's "minimal
  comments, WHY only" rule and the entry format in §2. Always run this before the
  closing-verification `pymarkdownlnt` pass (`uv run pymarkdown scan
  docs/ CLAUDE.md`) whenever a change touched a tracked `.md` file or
  added/edited comments -- trimming content first means markdownlint
  isn't reflowing prose that is about to be cut anyway. Use it whenever
  the user asks to "trim comments," "clean up docstrings," "tidy
  the rules docs," or as part of closing out any card/engine/docs
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
`src/vtesbot/cards` and `docs/rulings/` + `docs/engine/`; pass paths to
narrow it to what the current change actually touched. It flags:

- inline comments that likely just restate the line they sit on;
- comments/docstrings written as task notes ("fix for...", "added
  for this PR", "see issue #123") instead of timeless rationale;
- a card module (`src/vtesbot/cards/<name>.py`) whose module
  docstring has no rule-source citation at all;
- any `resolved` RUL/ENG entry whose bullet labels aren't exactly
  Situation / Rules & interactions / Solution.

Exit code is 0 in every case; everything it prints is a non-zero-information candidate list, not a
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
rule-implementing module (see any file in `src/vtesbot/cards/`) is a
*long* docstring: verbatim card text, verbatim rulings with their
citation codes, the RUL/ENG entries that settled an ambiguity, and the
engine-wiring rationale. That density is the point -- every sentence
in it answers a "why would the code do it this way" question a
reader would otherwise have to go dig up from KRCG, the rulebook or
the rules docs themselves. Do not shorten these just to
shorten them.

**Exception: every file under `src/vtesbot/` except individual card
modules in `cards/`** (`engine/` including `phases/`, `agents/`,
`decks/`, `formats/`, `sim/`, top-level modules, and within `cards/`
itself: `registry.py`, `_shared.py`, `__init__.py` -- anything that
isn't one card's own implementation file). These are
plumbing/infrastructure, not card-text implementations, and every
comment or docstring in them must be at most 200 characters
(whitespace-collapsed, i.e. the content length, not the wrapped
line count). A card's own module (e.g. `cards/diana_iadanza.py`)
keeps the normal long-docstring house style above. Compact a
citation to a short pointer (`ENG-022`, `DES-005`, `Rulebook §5`)
instead of quoting the ruling or rationale verbatim -- the full text
already lives in that entry's file under `docs/`, so the docstring
only needs to point there, not repeat it. `src/vtesbot/engine/hooks.py` is the worked example: every
docstring in it was trimmed to this cap. Verify with:

```bash
python3 -c "
import re, glob

def is_card_module(path):
    # one card's own implementation file, e.g. cards/diana_iadanza.py
    return (
        path.startswith('src/vtesbot/cards/')
        and path not in ('src/vtesbot/cards/__init__.py', 'src/vtesbot/cards/_shared.py', 'src/vtesbot/cards/registry.py')
    )

files = [
    f for f in glob.glob('src/vtesbot/**/*.py', recursive=True)
    if not is_card_module(f)
]
for f in files:
    text = open(f, encoding='utf-8').read()
    for m in re.finditer(r'\"\"\"(.*?)\"\"\"', text, re.S):
        s = re.sub(r'\s+', ' ', m.group(1).strip())
        if len(s) > 200:
            print(f, len(s), s[:60])
"
```

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
  -- raise it as a `RUL` entry (`vtes-rules-reference` skill)
  rather than inventing one. **Never write a citation you have not
  verified against the source** (CLAUDE.md §2's no-guessing rule
  applies to documentation exactly as much as to engine behavior).

When trimming a docstring that documents an implemented card or
rule, re-read it next to the actual card text / ruling / rule
section first -- don't cut a sentence just because it looks verbose
if it's covering a ruling-driven edge case a reader couldn't infer
from the code.

## 3. Rules docs (docs/rulings/, docs/engine/)

Format and procedure live in CLAUDE.md §2 and the
`vtes-rules-reference` skill. What to check here:

- Every `resolved` entry is trimmed to exactly three fields, in
  order: `Situation`, `Rules & interactions`, `Solution` (a label may
  carry a parenthetical qualifier, e.g. `Solution (user ruling):` --
  that's fine, the label itself must still be one of the three).
  Don't invent a different shape for a new entry.
- Title convention: `# <ID> - <Card name, where one exists> - <short
  description>`; the file name is `<ID>-<slug>.md` and the front
  matter's `status` matches the entry's real state.
- A `resolved` entry's `Solution` should name *where* the fix lives
  (module/function) so a future reader doesn't have to re-derive it,
  but should not re-explain code that file's own docstring already
  covers in depth -- point at it instead of duplicating it.
- After any title or front-matter edit, `python scripts/docs_index.py`
  regenerates the folder's `README.md`.

## 4. docs/design/

- `DES` entries follow the Context/Decision/Consequence shape (some add
  Rationale) -- keep a trimmed entry terse but don't force it into the
  RUL/ENG three-field shape; they document different things
  (architecture choices that stay true going forward vs. resolved rules
  or engine questions).
- A superseded decision keeps its file (`status: superseded`,
  `superseded_by: DES-<nnn>`); trim it to a short stub rather than
  deleting it, since ids are never reused.

## 5. Close out

After trimming, run the project's own closing-verification sequence
(CLAUDE.md §6) once, over the final content:

```bash
uv run pytest
uv run ruff check .
uv run pymarkdown scan docs/ CLAUDE.md
python scripts/docs_index.py --check
```

If a `data/` JSON file was touched in the process (it shouldn't be,
for this skill, but double-check), also run the `pretty-format-json`
check from CLAUDE.md §6.
