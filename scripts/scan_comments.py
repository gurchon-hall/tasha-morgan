"""Flag candidate comments/docstrings and doc entries for the `trim-comments` skill.

This is a *candidate scanner*, not a linter: CLAUDE.md §6's comment rule
("minimal... only when the WHY is non-obvious... never restate what the
code already says") and the rules-docs entry format (§2, DES-016) both
turn on judgment a regex cannot make --
whether a given sentence is "the why" or just restates the next line is a
reading-comprehension call. This script only narrows down what a human (or
an agent doing the `trim-comments` QA pass) should read closely; it never
edits a file itself and a clean run is not proof the pass is done.

Checks:
  - Inline `#` comments whose words substantially overlap the code on the
    same line (possible restatement) -- skipped if the comment contains a
    citation-like token (SS, "Rulebook", "2P variant", "RUL-"/"ENG-"/"DES-", "ruling",
    "krcg"), since overlap with cited rule language is expected, not a
    restatement smell.
  - Inline/docstring comments matching task-reference language ("fix for",
    "added for", "this PR", "used by the caller", "see issue/ticket/#123")
    instead of timeless rationale.
  - Module-level docstrings of `src/vtesbot/cards/*.py` files with no
    rule-source citation token at all. Every implemented card's module
    docstring follows one settled convention (card text + rulings quoted
    verbatim, see any existing card file) -- this is the one place a
    missing citation is a reliable signal rather than a guess. Function/
    class docstrings elsewhere are not checked: deciding whether a given
    function "implements a rule" (CLAUDE.md §2) and therefore needs a
    citation is a judgment call this script cannot make reliably, and a
    blanket check there produces mostly noise (plumbing helpers, registry
    glue, dataclass fields -- see the skill's own notes on this).
  - `docs/rulings/` and `docs/engine/`: any `resolved` entry whose bullet
    labels are not exactly Situation / Rules & interactions / Solution.

Usage:
    python scripts/scan_comments.py [path ...]

With no paths, scans src/vtesbot/engine, src/vtesbot/cards, docs/rulings and
docs/engine. Exit code is always 0: every finding is a candidate to review,
not a failure.
"""

from __future__ import annotations

import argparse
import re
import sys
import tokenize
from pathlib import Path

_CITATION_RE = re.compile(
    r"§|\bss\d|\brulebook\b|\b2p variant\b|\b(?:rul|eng|des)-\d|\bruling\b|\bkrcg\b",
    re.IGNORECASE,
)

TASK_REFERENCE_PATTERNS = (
    r"\bthis (?:fix|pr|patch|change)\b",
    r"\bfix(?:es|ed)? for\b",
    r"\badded for (?:the|this)\b",
    r"\bused by (?:the )?caller\b",
    r"\bsee (?:issue|ticket)\b",
    r"#\d+\b",
    r"\bas (?:requested|discussed)\b",
)
_TASK_RE = re.compile("|".join(TASK_REFERENCE_PATTERNS), re.IGNORECASE)

_WORD_RE = re.compile(r"[a-zA-Z_][a-zA-Z_0-9]*")

ENTRY_RE = re.compile(r"^(?:RUL|ENG)-\d{3}-.*\.md$")


def _has_citation(text: str) -> bool:
    return bool(_CITATION_RE.search(text))


def _word_overlap(a: str, b: str) -> float:
    # snake_case identifiers split into their constituent words so e.g.
    # `pending_counter` overlaps a comment's "pending counter".
    words_a = {w.lower() for w in _WORD_RE.findall(a.replace("_", " ")) if len(w) > 2}
    words_b = {w.lower() for w in _WORD_RE.findall(b.replace("_", " ")) if len(w) > 2}
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a)


def scan_python_file(path: Path, check_module_citation: bool) -> list[str]:
    findings = []
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()

    with path.open("rb") as fh:
        tokens = list(tokenize.tokenize(fh.readline))

    seen_module_docstring = False
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            line_no = tok.start[0]
            comment_text = tok.string.lstrip("#").strip()
            code_on_line = lines[line_no - 1][: tok.start[1]]
            if _TASK_RE.search(comment_text):
                findings.append(
                    f"{path}:{line_no}: task-reference language in comment: {tok.string!r}"
                )
            elif not _has_citation(comment_text):
                overlap = _word_overlap(comment_text, code_on_line)
                if overlap >= 0.6 and len(comment_text.split()) >= 2:
                    findings.append(
                        f"{path}:{line_no}: possible restatement "
                        f"(overlap={overlap:.0%}): {tok.string!r}"
                    )
        elif tok.type == tokenize.STRING and check_module_citation and not seen_module_docstring:
            # The first STRING token in the file is the module docstring
            # (a plain pass/import would appear as NAME/OP tokens first).
            seen_module_docstring = True
            if not _has_citation(tok.string):
                findings.append(
                    f"{path}:{tok.start[0]}: module docstring has no rule-source "
                    "citation token (Rulebook/2P variant/RUL-/ENG-/DES-/ruling/krcg) -- every "
                    "implemented card cites its card text/rulings here"
                )
        elif tok.type not in (
            tokenize.NEWLINE,
            tokenize.NL,
            tokenize.INDENT,
            tokenize.ENCODING,
            tokenize.COMMENT,
        ):
            seen_module_docstring = True
    return findings


def scan_rules_entry(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if not re.search(r"^status: resolved$", text, flags=re.MULTILINE):
        return []
    expected_labels = ["Situation", "Rules & interactions", "Solution"]
    # A label may carry a parenthetical qualifier, e.g. "Solution (user
    # ruling):" -- compare only the part before any "(".
    raw_labels = re.findall(r"^- ([^\n:]*?):", text, flags=re.MULTILINE)
    labels = [label.split(" (", 1)[0].strip() for label in raw_labels]
    if labels != expected_labels:
        return [f"{path}: resolved entry has fields {labels!r}, expected {expected_labels!r}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Files/directories to scan")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    if args.paths:
        targets = [Path(p) for p in args.paths]
    else:
        targets = [
            repo_root / "src" / "vtesbot" / "engine",
            repo_root / "src" / "vtesbot" / "cards",
            repo_root / "docs" / "rulings",
            repo_root / "docs" / "engine",
        ]

    all_findings: list[str] = []

    for target in targets:
        if target.is_dir():
            for entry in sorted(target.glob("*.md")):
                if ENTRY_RE.match(entry.name):
                    all_findings.extend(scan_rules_entry(entry))
            for py_file in sorted(target.rglob("*.py")):
                is_card_module = "cards" in py_file.parts and not (
                    py_file.stem.startswith("_") or py_file.stem == "registry"
                )
                check_module_citation = is_card_module
                all_findings.extend(scan_python_file(py_file, check_module_citation))
        elif target.suffix == ".py":
            check_module_citation = "cards" in target.parts and not (
                target.stem.startswith("_") or target.stem == "registry"
            )
            all_findings.extend(scan_python_file(target, check_module_citation))
        elif ENTRY_RE.match(target.name):
            all_findings.extend(scan_rules_entry(target))

    if not all_findings:
        print("No candidates found.")
    for finding in all_findings:
        print(finding)

    return 0


if __name__ == "__main__":
    sys.exit(main())
