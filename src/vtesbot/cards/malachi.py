"""Malachi (crypt vampire ability). krcg id 201676.

Printed text (fetched via `krcg.load()` + `msgspec.json.encode()`, project's
`uv run` venv (krcg 5.14), 2026-10-17, matching the raw snapshot
`data/cards/201676.json`): "Independent."

Rulings: none on file (`rulings == []`, confirmed in the raw snapshot).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Salubri, group 7,
capacity 6, disciplines `("AUS", "DOM", "FOR")`. No title (`"title": null` on
the live API). Legal since 2024-01-31; confirmed on the active 2P allowed
list (`data/formats/2p/2026-10-03.json`) and in the suggested 2P decklist
`data/decks/vekn-2p/salubri.json` (3 copies).

A bare sect preamble with nothing after it: unlike Leumeah (201526,
`cards/leumeah.py`) or Atiena (201579, `cards/atiena.py`), whose own
single-clause "<Sect> <Title> of <City>." text still names a title to
register with the generic vote machinery, Malachi's printed text is only the
sect word itself -- no colon, no title, no ability clause at all.
`derive_sect("Independent.")` (`engine/cards.py`) reads `Sect.INDEPENDENT`
from the bare preamble; nothing else follows for any hook to key off. This is
the first printed vampire in this pool with *neither* a title *nor* an
ability clause, so there is nothing left for this module to implement beyond
registering the card -- same spirit as Leumeah's own closing paragraph.
"""

from vtesbot.cards.registry import CardRegistration, Status, register

KRCG_ID = 201676

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Malachi",
        status=Status.IMPLEMENTED,
        hooks=(),
        source=__name__,
    )
)
