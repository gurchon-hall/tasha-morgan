"""Resolves parsed decklist lines to krcg ids.

Expands each `ParsedLine.count` into that many physical copies' worth of a
`formats.ResolvedCryptEntry`/`ResolvedLibraryEntry` (one entry per distinct
name on the decklist, `count` carrying the copy count) once that name's
krcg id is known -- `formats.check_deck_legality` and `loader.check_and_build`
consume these directly. Unresolved/ambiguous names are collected, never
guessed (CLAUDE.md no-guessing rule), mirroring `scripts/krcg_match.py`'s
own "unmatched" output shape.
"""

import krcg
from krcg import utils as krcg_utils

from vtesbot.formats import ResolvedCryptEntry, ResolvedLibraryEntry

from .name_resolution import build_indexes, group_num, match_crypt, match_library
from .parser import ParsedDecklist, Section


def _base_name(card) -> str:
    """The vampire's unique name with krcg's disambiguating group suffix
    stripped (mirrors `decks/loader.py::_build_crypt_card`), so a name that
    took several candidates to disambiguate (e.g. "Lucinde, Alastor (G7)")
    still reports/stores as its plain unique name."""
    name = krcg_utils.vekn_name(card, ascii=False)
    if card.unicity_suffix:
        name = name.removesuffix(f" ({card.unicity_suffix})")
    return name


class UnresolvedName:
    """A decklist line whose name krcg could not uniquely resolve."""

    def __init__(
        self,
        line_no: int,
        name: str,
        section: Section,
        suggested_krcg_id: int | None,
        suggested_name: str | None,
        candidates: list[dict] | None,
    ) -> None:
        self.line_no = line_no
        self.name = name
        self.section = section
        self.suggested_krcg_id = suggested_krcg_id
        self.suggested_name = suggested_name
        self.candidates = candidates


class ResolvedDecklist:
    def __init__(
        self,
        crypt: list[ResolvedCryptEntry],
        library: list[ResolvedLibraryEntry],
        unresolved: list[UnresolvedName],
    ) -> None:
        self.crypt = crypt
        self.library = library
        self.unresolved = unresolved


def resolve_decklist(
    parsed: ParsedDecklist, cards: krcg.CardDict, *, crypt_min_group: int = 5
) -> ResolvedDecklist:
    library_index, crypt_by_base = build_indexes(cards)

    crypt: list[ResolvedCryptEntry] = []
    unresolved: list[UnresolvedName] = []
    for line in parsed.crypt:
        result = match_crypt(cards, line.name, crypt_by_base, crypt_min_group)
        if not result["matched"]:
            unresolved.append(
                UnresolvedName(
                    line.line_no,
                    line.name,
                    line.section,
                    result["suggested_krcg_id"],
                    result["suggested_name"],
                    result.get("candidates"),
                )
            )
            continue
        card = cards[result["krcg_id"]]
        crypt.append(
            ResolvedCryptEntry(
                krcg_id=result["krcg_id"],
                name=_base_name(card),
                count=line.count,
                group=group_num(card),
            )
        )

    library: list[ResolvedLibraryEntry] = []
    for line in parsed.library:
        result = match_library(cards, line.name, library_index)
        if not result["matched"]:
            unresolved.append(
                UnresolvedName(
                    line.line_no,
                    line.name,
                    line.section,
                    result["suggested_krcg_id"],
                    result["suggested_name"],
                    result.get("candidates"),
                )
            )
            continue
        library.append(
            ResolvedLibraryEntry(
                krcg_id=result["krcg_id"], name=result["krcg_name"], count=line.count
            )
        )

    return ResolvedDecklist(crypt=crypt, library=library, unresolved=unresolved)
