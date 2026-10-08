"""Match VEKN card names (as published on a VEKN page) to KRCG card ids.

Used by the `format-curator` agent / `sync-2p-format` skill and by deck
imports, so the exact matching logic is reproducible instead of being
re-typed ad hoc in each session. Project rule (CLAUDE.md): a name that does
not match exactly is reported to the user, never silently auto-corrected —
so this script only auto-fills a krcg_id for an *exact* match (allowing the
"Name, The" <-> "The Name" VEKN convention and case/whitespace folding).
Anything else is left unmatched with krcg's own fuzzy suggestion attached
for a human to confirm.

Crypt ambiguity: VEKN writes a vampire's name with no group suffix, but
krcg keeps several printings (one per group) under that same base name,
and gives the *un-suffixed* vekn_name to whichever printing happens to be
the earliest — which is often a low-group one. Confirmed with the user
2026-10-08: every vampire on the VEKN 2-player allowed list is printed at
group >= 5 (the project's 2P card pool only uses group 5-7 reprints), so
when a crypt name has more than one krcg printing, the group >= 5 one is
selected. If zero or more than one printing qualifies, the name is left
unmatched with all candidate (krcg_id, group) pairs listed for a human to
pick — never guessed.

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
import re
import sys
import unicodedata
from importlib.metadata import version

from krcg import vtes

_GROUP_SUFFIX = re.compile(r"\s*\(G\d+\)$", re.IGNORECASE)


def _fold(name: str) -> str:
    """Case/whitespace/accent-insensitive key."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return " ".join(name.strip().split()).casefold()


def _base_name(vekn_name: str) -> str:
    """Strip krcg's disambiguating '(G6)'-style suffix, if any."""
    return _GROUP_SUFFIX.sub("", vekn_name)


def build_indexes() -> tuple[dict[str, "vtes.Card"], dict[str, list["vtes.Card"]]]:
    # Library cards: fold both vekn_name (VEKN's "X, The" convention) and
    # name (krcg's "The X" convention) so either spelling resolves.
    library_index: dict[str, vtes.Card] = {}
    # Crypt cards: grouped by base name (suffix stripped) so a bare VEKN
    # name can be disambiguated by group instead of grabbing whichever
    # printing happens to own the un-suffixed vekn_name.
    crypt_by_base: dict[str, list[vtes.Card]] = {}
    for card in vtes.VTES:
        if card.crypt:
            crypt_by_base.setdefault(_fold(_base_name(card.vekn_name)), []).append(card)
        else:
            library_index.setdefault(_fold(card.vekn_name), card)
            library_index.setdefault(_fold(card.name), card)
    return library_index, crypt_by_base


def _the_variants(name: str) -> list[str]:
    """Forms to retry krcg's fuzzy get() on: swap 'X, The' <-> 'The X',
    and also the bare title with no article at all (a stray/missing ', The'
    is as likely as a genuine typo elsewhere in the name)."""
    stripped = name.strip()
    variants = []
    if stripped.lower().endswith(", the"):
        bare = stripped[: -len(", the")]
        variants += ["The " + bare, bare]
    elif stripped.lower().startswith("the "):
        bare = stripped[4:]
        variants += [bare + ", The", bare]
    return variants


def _unmatched(name: str, candidates: list["vtes.Card"] | None = None) -> dict:
    suggestion = vtes.VTES.get(name)
    for variant in _the_variants(name):
        if suggestion:
            break
        suggestion = vtes.VTES.get(variant)
    result = {
        "krcg_id": None,
        "matched": False,
        "suggested_krcg_id": suggestion.id if suggestion else None,
        "suggested_name": suggestion.vekn_name if suggestion else None,
    }
    if candidates:
        result["candidates"] = [
            {"krcg_id": c.id, "krcg_name": c.vekn_name, "group": c.group}
            for c in candidates
        ]
    return result


def match_crypt(
    name: str, crypt_by_base: dict[str, list["vtes.Card"]], min_group: int
) -> dict:
    candidates = crypt_by_base.get(_fold(_base_name(name)))
    if not candidates:
        return _unmatched(name)
    if len(candidates) == 1:
        card = candidates[0]
        return {"krcg_id": card.id, "krcg_name": card.vekn_name, "matched": True}
    qualifying = [c for c in candidates if int(c.group) >= min_group]
    if len(qualifying) == 1:
        card = qualifying[0]
        return {"krcg_id": card.id, "krcg_name": card.vekn_name, "matched": True}
    # 0 or >1 printings at group >= min_group: don't guess, list them all.
    return _unmatched(name, candidates)


def match_library(name: str, library_index: dict[str, "vtes.Card"]) -> dict:
    card = library_index.get(_fold(name))
    if card is not None:
        return {"krcg_id": card.id, "krcg_name": card.vekn_name, "matched": True}
    return _unmatched(name)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

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

    vtes.VTES.load()
    library_index, crypt_by_base = build_indexes()

    matched, unmatched = [], []
    for entry in entries:
        if entry.get("type") == "Crypt":
            result = match_crypt(entry["name"], crypt_by_base, args.crypt_min_group)
        else:
            result = match_library(entry["name"], library_index)
        is_matched = result.pop("matched")
        merged = {**entry, **result}
        (matched if is_matched else unmatched).append(merged)

    output = {
        "krcg_version": version("krcg"),
        "crypt_min_group": args.crypt_min_group,
        "card_count": len(vtes.VTES),
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
