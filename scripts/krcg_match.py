"""Match VEKN card names (as published on a VEKN page) to KRCG card ids.

Used by the `format-curator` agent / `sync-2p-format` skill and by deck
imports, so the exact matching logic is reproducible instead of being
re-typed ad hoc in each session. Project rule (CLAUDE.md): a name that does
not match exactly is reported to the user, never silently auto-corrected —
so this script only auto-fills a krcg_id for an *exact* match (allowing the
"Name, The" <-> "The Name" VEKN convention and case/whitespace folding).
Anything else is left unmatched with krcg's own fuzzy suggestion attached
for a human to confirm.

Built against krcg >= 5.14 (see pyproject.toml). krcg 5.x replaced the old
`krcg.vtes.VTES` singleton with `krcg.load()` -> `CardDict`; this script uses
only the new API (`cards.cards()`, `card.kind`, `card.printed_name`,
`krcg.utils.vekn_name()`). It is not compatible with krcg 4.x.

Crypt ambiguity: VEKN writes a vampire's name with no group suffix, but
krcg keeps several printings (one per group) under that same base name,
and `cards.get()` / bare-name lookups resolve to whichever printing happens
to be entered first — which is often a low-group one (confirmed still true
under the 5.x API by hand-testing "Lucinde, Alastor", which resolves to the
G3 printing, not G7). Confirmed with the user 2026-10-08: every vampire on
the VEKN 2-player allowed list is printed at group >= 5 (the project's 2P
card pool only uses group 5-7 reprints), so when a crypt name has more than
one krcg printing, the group >= 5 one is selected. If zero or more than one
printing qualifies, the name is left unmatched with all candidate
(krcg_id, group) pairs listed for a human to pick — never guessed.

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
import unicodedata
from importlib.metadata import version

import krcg
from krcg import utils as krcg_utils


def _fold(name: str) -> str:
    """Case/whitespace/accent-insensitive key."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return " ".join(name.strip().split()).casefold()


def build_indexes(cards: krcg.CardDict):
    """Library cards keyed by VEKN "X, The" convention and krcg's own
    "The X" printed_name, so either spelling resolves. Crypt cards grouped
    by base name (krcg's disambiguating suffix stripped) so a bare VEKN
    name can be disambiguated by group instead of grabbing whichever
    printing happens to own the un-suffixed name."""
    library_index = {}
    crypt_by_base = {}
    for card in cards.cards():
        if card.kind.value == "Crypt":
            base = krcg_utils.vekn_name(card, ascii=False)
            if card.unicity_suffix:
                base = base.removesuffix(f" ({card.unicity_suffix})")
            crypt_by_base.setdefault(_fold(base), []).append(card)
        else:
            library_index.setdefault(_fold(krcg_utils.vekn_name(card, ascii=False)), card)
            library_index.setdefault(_fold(card.printed_name), card)
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


def _group_num(card) -> int:
    """krcg 5.x reports crypt group as a string like 'G7'."""
    return int(card.group.lstrip("Gg"))


def _unmatched(cards, name: str, candidates: list | None = None) -> dict:
    suggestion = cards.get(name)
    for variant in _the_variants(name):
        if suggestion:
            break
        suggestion = cards.get(variant)
    result = {
        "krcg_id": None,
        "matched": False,
        "suggested_krcg_id": suggestion.id if suggestion else None,
        "suggested_name": krcg_utils.vekn_name(suggestion, ascii=False) if suggestion else None,
    }
    if candidates:
        result["candidates"] = [
            {
                "krcg_id": c.id,
                "krcg_name": krcg_utils.vekn_name(c, ascii=False),
                "group": _group_num(c),
            }
            for c in candidates
        ]
    return result


def match_crypt(cards, name: str, crypt_by_base: dict[str, list], min_group: int) -> dict:
    candidates = crypt_by_base.get(_fold(name))
    if not candidates:
        return _unmatched(cards, name)
    if len(candidates) == 1:
        card = candidates[0]
        name_ = krcg_utils.vekn_name(card, ascii=False)
        return {"krcg_id": card.id, "krcg_name": name_, "matched": True}
    qualifying = [c for c in candidates if _group_num(c) >= min_group]
    if len(qualifying) == 1:
        card = qualifying[0]
        name_ = krcg_utils.vekn_name(card, ascii=False)
        return {"krcg_id": card.id, "krcg_name": name_, "matched": True}
    # 0 or >1 printings at group >= min_group: don't guess, list them all.
    return _unmatched(cards, name, candidates)


def match_library(cards, name: str, library_index: dict) -> dict:
    card = library_index.get(_fold(name))
    if card is not None:
        name_ = krcg_utils.vekn_name(card, ascii=False)
        return {"krcg_id": card.id, "krcg_name": name_, "matched": True}
    return _unmatched(cards, name)


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
