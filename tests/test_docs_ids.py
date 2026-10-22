"""Rules-docs ids (DES-016): every `RUL-`/`ENG-`/`DES-` id cited anywhere in
the repository has an entry file, the entries are well-formed, and each
folder's generated index is current."""

import importlib.util
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCANNED = ("src", "tests", "scripts", ".claude", "docs", "CLAUDE.md", "README.md")
ID_RE = re.compile(r"\b(RUL|ENG|DES)-(\d{3})\b")
OLD_ID_RE = re.compile(r"\bOQ-\d+|(?<![\w-])D-\d+\b")

_spec = importlib.util.spec_from_file_location("docs_index", REPO / "scripts" / "docs_index.py")
assert _spec is not None and _spec.loader is not None
docs_index = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(docs_index)


def _scanned_files() -> list[Path]:
    files: list[Path] = []
    for name in SCANNED:
        path = REPO / name
        if path.is_file():
            files.append(path)
        else:
            files += [
                p
                for p in path.rglob("*")
                if p.suffix in (".py", ".md") and "__pycache__" not in p.parts
            ]
    return files


def _entry_ids() -> set[str]:
    return {e.id for kind in docs_index.KINDS for e in docs_index.load_entries(kind)}


def test_every_cited_id_has_an_entry_file():
    known = _entry_ids()
    dangling = sorted(
        f"{path.relative_to(REPO)}: {m.group(0)}"
        for path in _scanned_files()
        for m in ID_RE.finditer(path.read_text(encoding="utf-8"))
        if m.group(0) not in known
    )
    assert dangling == []


def test_no_former_oq_or_decision_ids_remain():
    leftovers = sorted(
        f"{path.relative_to(REPO)}: {m.group(0)}"
        for path in _scanned_files()
        if path != Path(__file__).resolve()
        for m in OLD_ID_RE.finditer(path.read_text(encoding="utf-8"))
    )
    assert leftovers == []


@pytest.mark.parametrize("kind", docs_index.KINDS, ids=lambda k: k.prefix)
def test_entries_are_well_formed_and_index_is_current(kind):
    entries = docs_index.load_entries(kind)  # raises on any malformed entry
    assert entries, f"docs/{kind.folder} has no entries"
    index = REPO / "docs" / kind.folder / "README.md"
    assert index.read_text(encoding="utf-8") == docs_index.render_index(kind, entries), (
        "stale index: run `python scripts/docs_index.py`"
    )


def test_superseded_by_points_at_an_existing_entry():
    known = _entry_ids()
    for kind in docs_index.KINDS:
        for e in docs_index.load_entries(kind):
            if e.superseded_by is not None:
                assert e.superseded_by in known, f"{e.id} superseded_by {e.superseded_by}"
