"""Parses a plain-text VtES decklist into crypt/library name+count lines.

Per the `deck-validation` skill: "Accept plain-text decklists with a crypt
section and a library section, lines like `2x Card Name` or `2 Card Name`.
Do not assume one site's export format; if a line cannot be parsed, report
it with its line number instead of skipping it." Name resolution (krcg
lookup) is a separate step (`decks/resolver.py`) -- this module only
recognizes section headers and `<count> <name>` lines.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

Section = Literal["crypt", "library"]

_CRYPT_HEADER_RE = re.compile(r"^crypt\b", re.IGNORECASE)
_LIBRARY_HEADER_RE = re.compile(r"^library\b", re.IGNORECASE)
_LINE_RE = re.compile(r"^(\d+)\s*[xX]?\s+(.+)$")


@dataclass(frozen=True)
class ParsedLine:
    line_no: int
    count: int
    name: str
    section: Section


@dataclass(frozen=True)
class ParseError:
    line_no: int
    text: str
    reason: str


@dataclass(frozen=True)
class ParsedDecklist:
    crypt: list[ParsedLine] = field(default_factory=list)
    library: list[ParsedLine] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)


def parse_decklist(text: str) -> ParsedDecklist:
    crypt: list[ParsedLine] = []
    library: list[ParsedLine] = []
    errors: list[ParseError] = []
    section: Section | None = None

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        if _CRYPT_HEADER_RE.match(line):
            section = "crypt"
            continue
        if _LIBRARY_HEADER_RE.match(line):
            section = "library"
            continue

        match = _LINE_RE.match(line)
        if match is None:
            errors.append(
                ParseError(line_no, raw_line, "does not match '<count>[x] <name>'")
            )
            continue
        if section is None:
            errors.append(
                ParseError(line_no, raw_line, "card line before any 'Crypt'/'Library' header")
            )
            continue

        count = int(match.group(1))
        name = match.group(2).strip()
        parsed = ParsedLine(line_no=line_no, count=count, name=name, section=section)
        (crypt if section == "crypt" else library).append(parsed)

    return ParsedDecklist(crypt=crypt, library=library, errors=errors)
