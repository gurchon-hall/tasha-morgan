"""2P deck-construction legality checks.

Typed port of `scripts/validate_deck.py::validate`'s rule checks (that
script stays a standalone dev tool for fixture maintenance; this module is
what the production deck-import pipeline relies on for the rules).

Rule sources, all per the `deck-validation` skill / CLAUDE.md §2-4:
  - Crypt size >= 12: Rulebook §1 Deck construction.
  - Crypt groups: one group, or two consecutive groups: Rulebook §1-2.
  - Library size 40-60 (replaces the rulebook's 60-90): 2P variant §2.3.
  - Every crypt/library card on the active 2P allowed list, with the
    matching Crypt/Library type for its section: 2P variant §2.3.
No maximum copy count exists in any source; none is enforced here.
"""

from dataclasses import dataclass

from .allowed_list import AllowedList

MIN_CRYPT_SIZE = 12
MIN_LIBRARY_SIZE = 40
MAX_LIBRARY_SIZE = 60


@dataclass(frozen=True)
class LegalityViolation:
    rule: str
    detail: str


@dataclass(frozen=True)
class ResolvedCryptEntry:
    """A crypt line already resolved to a krcg id (one entry per distinct
    name/printing on the decklist; `count` is the number of physical copies)."""

    krcg_id: int
    name: str
    count: int
    group: int


@dataclass(frozen=True)
class ResolvedLibraryEntry:
    krcg_id: int
    name: str
    count: int


def _consecutive(groups: list[int]) -> bool:
    if len(groups) <= 1:
        return True
    return len(groups) == 2 and groups[1] - groups[0] == 1


def check_deck_legality(
    crypt: list[ResolvedCryptEntry],
    library: list[ResolvedLibraryEntry],
    allowed: AllowedList,
) -> list[LegalityViolation]:
    violations: list[LegalityViolation] = []

    crypt_total = sum(e.count for e in crypt)
    if crypt_total < MIN_CRYPT_SIZE:
        violations.append(
            LegalityViolation(
                "Rulebook §1 Deck construction",
                f"Crypt size {crypt_total} < {MIN_CRYPT_SIZE} minimum",
            )
        )

    groups = sorted({e.group for e in crypt})
    if not _consecutive(groups):
        violations.append(
            LegalityViolation(
                "Rulebook §1-2 Deck construction",
                f"Crypt groups {groups} are not one group or two consecutive groups",
            )
        )

    library_total = sum(e.count for e in library)
    if not (MIN_LIBRARY_SIZE <= library_total <= MAX_LIBRARY_SIZE):
        violations.append(
            LegalityViolation(
                "2P variant §2.3",
                f"Library size {library_total} outside {MIN_LIBRARY_SIZE}-{MAX_LIBRARY_SIZE}",
            )
        )

    for expected_type, entries in (("Crypt", crypt), ("Library", library)):
        for entry in entries:
            allowed_card = allowed.by_krcg_id.get(entry.krcg_id)
            if allowed_card is None:
                violations.append(
                    LegalityViolation(
                        "2P variant §2.3",
                        f"{expected_type} card not on 2P allowed list: "
                        f"{entry.name} ({entry.krcg_id})",
                    )
                )
            elif allowed_card.type != expected_type:
                violations.append(
                    LegalityViolation(
                        "2P variant §2.3",
                        f"{entry.name} ({entry.krcg_id}) is {allowed_card.type} on the allowed "
                        f"list, not {expected_type}",
                    )
                )

    return violations
