"""Enforce CLAUDE.md §6's cap: every docstring and `#` comment block is at most 3 lines.
Default scope: comments overlapping lines changed since HEAD (plus untracked files);
`--all` or explicit paths check whole files. Exit 1 on any violation."""

import argparse
import ast
import io
import re
import subprocess
import sys
import tokenize
from pathlib import Path

MAX_LINES = 3
ROOT = Path(__file__).resolve().parent.parent
SCOPES = ("src", "tests", "scripts")
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def _in_scope(path: str) -> bool:
    return path.endswith(".py") and path.split("/", 1)[0] in SCOPES


def changed_lines() -> dict[Path, set[int] | None]:
    """Changed line numbers per file since HEAD; `None` means the whole file is new."""
    changed: dict[Path, set[int] | None] = {}
    for name in _git("ls-files", "--others", "--exclude-standard").splitlines():
        if _in_scope(name):
            changed[ROOT / name] = None
    current: set[int] | None = None
    for line in _git("diff", "-U0", "--no-color", "HEAD", "--", *SCOPES).splitlines():
        if line.startswith("+++ "):
            name = line[6:] if line.startswith("+++ b/") else ""
            current = changed.setdefault(ROOT / name, set()) if _in_scope(name) else None
        elif (m := _HUNK.match(line)) and current is not None:
            start, count = int(m[1]), int(m[2] or 1)
            current.update(range(start, start + count))
    return changed


def comment_spans(source: str) -> list[tuple[int, int, int, str]]:
    """(first line, last line, content lines, kind) of every docstring and comment block."""
    spans = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            content = len(node.value.value.strip().splitlines())
            spans.append((node.lineno, node.end_lineno or node.lineno, content, "docstring"))
    block: list[int] = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT and tok.line.lstrip().startswith("#"):
            if tok.start[0] == 1 and tok.string.startswith("#!"):
                continue
            if block and tok.start[0] != block[-1] + 1:
                spans.append((block[0], block[-1], len(block), "comment block"))
                block = []
            block.append(tok.start[0])
    if block:
        spans.append((block[0], block[-1], len(block), "comment block"))
    return spans


def violations(path: Path, lines: set[int] | None) -> list[str]:
    found = []
    for first, last, content, kind in comment_spans(path.read_text(encoding="utf-8")):
        touched = lines is None or any(first <= n <= last for n in lines)
        if content > MAX_LINES and touched:
            rel = path.relative_to(ROOT).as_posix()
            found.append(f"{rel}:{first}: {kind} is {content} lines (max {MAX_LINES})")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="files/dirs to check whole")
    parser.add_argument("--all", action="store_true", help="check every file in scope")
    args = parser.parse_args()
    if args.paths or args.all:
        roots = args.paths or [ROOT / s for s in SCOPES]
        files = [p for r in roots for p in ([r] if r.is_file() else sorted(r.rglob("*.py")))]
        targets: dict[Path, set[int] | None] = {p.resolve(): None for p in files}
    else:
        targets = changed_lines()
    found = [v for p, lines in sorted(targets.items()) if p.exists() for v in violations(p, lines)]
    print("\n".join(found) or f"comment_lines: ok ({len(targets)} files)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
