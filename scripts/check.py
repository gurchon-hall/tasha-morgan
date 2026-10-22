"""Closing verification (CLAUDE.md §6): every check, one command, summary at the end.
Run with `uv run python scripts/check.py`; tools run via this interpreter (`-m`).
`--skip NAME` drops a step (repeatable). Exit 1 if any step fails."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def _json_files() -> list[str]:
    return [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "data").rglob("*.json"))]


STEPS: dict[str, list[str]] = {
    "pytest": [PY, "-m", "pytest", "-q"],
    "ruff-check": [PY, "-m", "ruff", "check", "."],
    "ruff-format": [PY, "-m", "ruff", "format", "--check", "."],
    "pyright": [PY, "-m", "basedpyright"],
    "comment-lines": [PY, "scripts/comment_lines.py"],
    "markdown": [PY, "-m", "pymarkdown", "scan", "-r", "docs/", "CLAUDE.md", ".claude/"],
    "docs-index": [PY, "scripts/docs_index.py", "--check"],
    "json": [
        PY,
        "-m",
        "pre_commit_hooks.pretty_format_json",
        "--no-sort-keys",
        "--no-ensure-ascii",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip", action="append", default=[], choices=STEPS)
    args = parser.parse_args()
    results: dict[str, bool] = {}
    for name, cmd in STEPS.items():
        if name in args.skip:
            continue
        if name == "json":
            cmd = [*cmd, *_json_files()]
        print(f"=== {name}", flush=True)
        results[name] = subprocess.run(cmd, cwd=ROOT).returncode == 0
    print("\n" + "\n".join(f"{'ok  ' if ok else 'FAIL'} {name}" for name, ok in results.items()))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
