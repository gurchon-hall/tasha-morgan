"""Match a VEKN-style card name to a krcg card id.

Shared by `decks/loader.py` and `scripts/krcg_match.py` so the production
deck-import pipeline and that dev script don't maintain the matching logic
twice.

No-guessing rule (CLAUDE.md): `match_library`/`match_crypt` only ever
auto-resolve an *exact* match (folding case/whitespace/accents and the
"Name, The" <-> "The Name" VEKN convention). Anything else comes back
unmatched with krcg's own fuzzy suggestion attached for a human to confirm.

Crypt ambiguity: VEKN writes a vampire's name with no group suffix, but
krcg keeps several printings (one per group) under that same base name.
Confirmed with the user 2026-10-08: every vampire on the VEKN 2-player
allowed list is printed at group >= 5, so when a crypt name has more than
one krcg printing, the group >= `min_group` one is selected; if zero or
more than one printing qualifies, the name is left unmatched with every
candidate listed -- never guessed.

Built against krcg >= 5.14 (see pyproject.toml): uses `krcg.load()` ->
`CardDict`, not the old krcg 4.x `krcg.vtes.VTES` singleton.
"""

import unicodedata

import krcg
from krcg import utils as krcg_utils


def _fold(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return " ".join(name.strip().split()).casefold()


def build_indexes(
    cards: krcg.CardDict,
) -> tuple[dict[str, object], dict[str, list]]:
    """Library cards keyed by both the VEKN "X, The" convention and krcg's
    "The X" printed_name, so either spelling resolves. Crypt cards grouped
    by base name (suffix stripped) so a bare VEKN name can be disambiguated
    by group instead of grabbing whichever printing happens to own the
    un-suffixed name."""
    library_index: dict[str, object] = {}
    crypt_by_base: dict[str, list] = {}
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
    """Forms to retry krcg's fuzzy get() on: swap 'X, The' <-> 'The X', and
    the bare title with no article (a missing ', The' is as likely as a
    typo elsewhere in the name)."""
    stripped = name.strip()
    variants = []
    if stripped.lower().endswith(", the"):
        bare = stripped[: -len(", the")]
        variants += ["The " + bare, bare]
    elif stripped.lower().startswith("the "):
        bare = stripped[4:]
        variants += [bare + ", The", bare]
    return variants


def group_num(card) -> int:
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
                "group": group_num(c),
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
    qualifying = [c for c in candidates if group_num(c) >= min_group]
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
