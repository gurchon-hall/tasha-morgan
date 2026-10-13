"""Match VEKN card names (as published on a VEKN page) to KRCG card ids.

Thin CLI wrapper around `vtesbot.decks.name_resolution` (shared with the
production deck-import pipeline) — see that module's docstring for the
no-guessing rule and the crypt group-disambiguation rule it implements.

Built against krcg >= 5.14 (see pyproject.toml): uses `krcg.load()` ->
`CardDict`, not the old krcg 4.x `krcg.vtes.VTES` singleton.

Usage:
    python scripts/krcg_match.py input.json [-o output.json] [--crypt-min-group N]

Input JSON: a flat array of objects, each with at least a "name" field and
a "type" field ("Crypt" or a library type), e.g.
[{"name": "Spirit's Touch", "type": "Library"},
 {"name": "Lucinde, Alastor", "type": "Crypt"}]. Other fields pass through.

Output JSON: {"krcg_version": "...", "card_count": N,
"matched": [...input fields..., "krcg_id", "krcg_name"],
"unmatched": [...input fields..., "krcg_id": null,
              "suggested_krcg_id", "suggested_name",
              "candidates": [{"krcg_id", "krcg_name", "group"}, ...]]}
"""

import argparse
import json
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import krcg

from vtesbot.decks.name_resolution import build_indexes, match_crypt, match_library


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # type: ignore

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON file: array of {name, type, ...}")
    parser.add_argument("-o", "--output", help="write JSON here instead of stdout")
    parser.add_argument(
        "--crypt-min-group",
        type=int,
        default=5,
        help="minimum group a crypt printing must have to be auto-selected "
        "when a name has several (2P allowed-list rule, confirmed 2026-10-08; "
        "default: 5)",
    )
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        entries = json.load(f)

    cards = krcg.load()
    library_index, crypt_by_base = build_indexes(cards)

    matched, unmatched = [], []
    for entry in entries:
        if entry.get("type") == "Crypt":
            result = match_crypt(cards, entry["name"], crypt_by_base, args.crypt_min_group)
        else:
            result = match_library(cards, entry["name"], library_index)
        is_matched = result.pop("matched")
        merged = {**entry, **result}
        (matched if is_matched else unmatched).append(merged)

    output = {
        "krcg_version": version("krcg"),
        "crypt_min_group": args.crypt_min_group,
        "card_count": len(list(cards.cards())),
        "matched": matched,
        "unmatched": unmatched,
    }

    text = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)

    print(
        f"{len(matched)} matched, {len(unmatched)} unmatched"
        f" (krcg {output['krcg_version']}, {output['card_count']} cards)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
