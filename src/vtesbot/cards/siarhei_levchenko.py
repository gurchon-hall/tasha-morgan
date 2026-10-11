"""Siarhei Levchenko (crypt vampire ability). krcg id 201612.

Printed text (fetched via krcg's live API, `https://api.krcg.org/card/201612`,
2026-10-11; raw snapshot `data/cards/201612.json`, cross-checked against the
installed `krcg` package's own `krcg.vtes.VTES[201612].to_json()["card_text"]`
/ `krcg.vtes.VTES[201612].card_text`, same wording): "Anarch."

Rulings: none on file (`krcg.vtes.VTES[201612].rulings == []` and the raw API
snapshot's own `"rulings": []`, both checked 2026-10-11).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Brujah, group 6,
capacity 5, disciplines `["pot", "CEL", "PRE"]`. The live API's own `"title"`
field is `null`/`None`. Legal since 2021-12-31; confirmed on the active 2P
allowed list (`data/formats/2p/2026-10-03.json`) and in the suggested 2P
decklist `data/decks/vekn-2p/brujah.json` (1 copy).

Exactly the same shape as Octane (201609, `src/vtesbot/cards/octane.py`),
whose module docstring this one mirrors: a bare sect keyword, "Anarch.",
with no title, no city, no colon, no second sentence -- see `octane.py`'s
own docstring for why this is inert flavor/identity text that nothing in
`engine/` or `cards/` currently reads, and why no hypothetical interaction
is modeled here.

There is nothing left for this module to implement beyond registering the
card: no title, no vote value, no combat bonus, no reaction, no modifier of
any kind -- this module exists only so Siarhei Levchenko has an effect
module + registry entry per CLAUDE.md SS6.
"""

from vtesbot.cards.registry import CardRegistration, Status, register

KRCG_ID = 201612

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Siarhei Levchenko",
        status=Status.IMPLEMENTED,
        hooks=(),
        source=__name__,
    )
)
