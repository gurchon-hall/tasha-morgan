"""Check a decklist fixture against a versioned VEKN 2-player format file.

Used by the `deck-validation` skill / `format-curator` agent so the checks in
`.claude/skills/deck-validation/SKILL.md` are reproducible instead of being
re-run as an ad hoc one-off command each time. Mirrors the project's
no-guessing rule (CLAUDE.md): an id missing from the deck fixture's own
`unmatched` list is reported as a violation, never silently skipped.

Checks implemented (see SKILL.md for the rule/source table):
  - Crypt size >= 12 (Rulebook SS1 Deck construction)
  - Crypt groups: one group, or two consecutive groups
  - Library size 40-60 (2P variant SS2.3, replaces 60-90)
  - Every crypt/library krcg_id is on the active 2P allowed list, with the
    matching Crypt/Library type (2P variant SS2.3 + the dated format file)
  - Any entries left in the deck fixture's "unmatched" array are reported,
    never guessed

Also reports (informational, never affects the LEGAL/ILLEGAL verdict or
exit code -- a deck can be legal yet not playable by the bot, SKILL.md):
  - Each crypt/library card's implementation status, looked up by krcg_id
    against `src/vtesbot/cards/registry.py` -- "implemented", "blocked"
    (with its `OQ-<n>` reason), or "not_implemented" (no registry entry).
    Pass --annotate to write these as "implementation_status" /
    "blocked_reason" fields back into the deck fixture itself, instead of
    only printing them -- rerun with --annotate after any card's registry
    status changes, rather than editing those fields by hand.

Usage:
    python scripts/validate_deck.py <deck.json> --format <format.json> [--annotate]

Deck JSON: {"name", "crypt": [{"name","count","krcg_id","group",...}],
"library": [{"name","count","krcg_id",...}], "unmatched": [...]}
(the `data/decks/vekn-2p/*.json` fixture shape).

Format JSON: {"vekn_last_updated", "cards": [{"name","type","krcg_id"}]}
(the `data/formats/2p/<date>.json` shape).

Exit code: 0 if legal, 1 if any violation (so this can gate CI later).
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import vtesbot.cards as _cards_pkg  # noqa: F401  (import for registration side effect)
from vtesbot.cards import registry


def _consecutive(groups: list[int]) -> bool:
    if len(groups) <= 1:
        return True
    return len(groups) == 2 and groups[1] - groups[0] == 1


def validate(deck: dict, fmt: dict) -> list[str]:
    violations = []

    for entry in deck.get("unmatched", []):
        violations.append(f"Unresolved name in deck fixture: {entry.get('name')!r}")

    allowed_by_id = {c["krcg_id"]: c for c in fmt["cards"]}

    crypt_total = sum(c["count"] for c in deck["crypt"])
    if crypt_total < 12:
        violations.append(f"Crypt size {crypt_total} < 12 minimum (Rulebook SS1)")

    groups = sorted({c["group"] for c in deck["crypt"]})
    if not _consecutive(groups):
        violations.append(f"Crypt groups {groups} are not one group or two consecutive groups")

    library_total = sum(c["count"] for c in deck["library"])
    if not (40 <= library_total <= 60):
        violations.append(f"Library size {library_total} outside 40-60 (2P variant SS2.3)")

    for section, expected_type in (("crypt", "Crypt"), ("library", "Library")):
        for c in deck[section]:
            allowed = allowed_by_id.get(c["krcg_id"])
            if allowed is None:
                violations.append(
                    f"{expected_type} card not on 2P allowed list: {c['name']} ({c['krcg_id']})"
                )
            elif allowed["type"] != expected_type:
                violations.append(
                    f"{c['name']} ({c['krcg_id']}) is {allowed['type']} on the allowed "
                    f"list, not {expected_type}"
                )

    return violations


def implementation_status(krcg_id: int) -> dict[str, str]:
    reg = registry.get(krcg_id)
    if reg is None:
        return {"implementation_status": "not_implemented"}
    if reg.status is registry.Status.BLOCKED:
        assert reg.blocked_reason is not None  # enforced by registry.register()
        return {"implementation_status": "blocked", "blocked_reason": reg.blocked_reason}
    return {"implementation_status": "implemented"}


def not_yet_playable(deck: dict) -> list[str]:
    lines = []
    for section in ("crypt", "library"):
        for c in deck[section]:
            status = implementation_status(c["krcg_id"])
            if status["implementation_status"] == "blocked":
                lines.append(f"{c['name']}: blocked ({status['blocked_reason']})")
            elif status["implementation_status"] == "not_implemented":
                lines.append(f"{c['name']}: not implemented")
    return lines


def annotate(deck: dict) -> dict:
    """Return `deck` with "implementation_status"/"blocked_reason" written
    into every crypt/library entry, replacing any stale ones already there."""

    skip = ("implementation_status", "blocked_reason")

    def annotated_entry(entry: dict) -> dict:
        base = {k: v for k, v in entry.items() if k not in skip}
        return {**base, **implementation_status(entry["krcg_id"])}

    deck = dict(deck)
    deck["crypt"] = [annotated_entry(c) for c in deck["crypt"]]
    deck["library"] = [annotated_entry(c) for c in deck["library"]]
    return deck


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", help="deck fixture JSON, e.g. data/decks/vekn-2p/brujah.json")
    parser.add_argument(
        "--format", required=True, help="dated format JSON, e.g. data/formats/2p/2026-10-03.json"
    )
    parser.add_argument(
        "--annotate",
        action="store_true",
        help="write each card's implementation_status/blocked_reason back into the deck fixture",
    )
    args = parser.parse_args()

    deck_path = Path(args.deck)
    deck = json.loads(deck_path.read_text(encoding="utf-8"))
    with open(args.format, encoding="utf-8") as f:
        fmt = json.load(f)

    if args.annotate:
        text = json.dumps(annotate(deck), indent=2, ensure_ascii=False) + "\n"
        deck_path.write_text(text, encoding="utf-8")
        print(f"annotated {deck_path}")

    violations = validate(deck, fmt)

    crypt_total = sum(c["count"] for c in deck["crypt"])
    groups = sorted({c["group"] for c in deck["crypt"]})
    library_total = sum(c["count"] for c in deck["library"])

    print(f"Deck: {deck.get('name', args.deck)}   Format: 2p @ {fmt['vekn_last_updated']}")
    print(
        f"Crypt: {crypt_total} cards, groups {{{', '.join(map(str, groups))}}}   "
        f"Library: {library_total} cards"
    )
    print("LEGAL" if not violations else "ILLEGAL")
    print("Violations:")
    if violations:
        for v in violations:
            print(f" - {v}")
    else:
        print(" - none")

    print("Not yet playable by the bot:")
    npy = not_yet_playable(deck)
    if npy:
        for line in npy:
            print(f" - {line}")
    else:
        print(" - none")

    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
