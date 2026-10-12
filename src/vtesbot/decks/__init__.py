"""Deck parsing & validation (CLAUDE.md SS5): turns a user-supplied decklist
into an `engine.setup.DeckSpec`, gated by `formats.check_deck_legality`.
"""

from .loader import DeckImportResult, NotYetPlayableCard, check_and_build, load_resolved_fixture
from .name_resolution import match_crypt, match_library
from .parser import ParsedDecklist, ParsedLine, ParseError, parse_decklist
from .resolver import ResolvedDecklist, UnresolvedName, resolve_decklist

__all__ = [
    "DeckImportResult",
    "NotYetPlayableCard",
    "check_and_build",
    "load_resolved_fixture",
    "match_crypt",
    "match_library",
    "ParsedDecklist",
    "ParsedLine",
    "ParseError",
    "parse_decklist",
    "ResolvedDecklist",
    "UnresolvedName",
    "resolve_decklist",
]
