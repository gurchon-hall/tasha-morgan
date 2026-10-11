"""Octane (crypt vampire ability). krcg id 201609.

Printed text (fetched via krcg's live API, `https://api.krcg.org/card/201609`,
2026-10-11; raw snapshot `data/cards/201609.json`, cross-checked against the
installed `krcg` package's own `krcg.vtes.VTES[201609].to_json()["card_text"]`
/ `krcg.vtes.VTES[201609].card_text`, same wording): "Anarch."

Rulings: none on file (`krcg.vtes.VTES[201609].rulings == []` and the raw API
snapshot's own `"rulings": []`, both checked 2026-10-11).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Brujah, group 6,
capacity 6, disciplines `["CEL", "POT", "PRE"]`. The live API's own `"title"`
field is `null`/`None` -- unlike Atiena/Leumeah, Octane carries no title at
all, just the bare sect keyword "Anarch." with no city, no colon, no second
sentence. Legal since 2021-12-31; confirmed on the active 2P allowed list
(`data/formats/2p/2026-10-03.json`) and in the suggested 2P decklist
`data/decks/vekn-2p/brujah.json` (1 copy).

"Anarch." is a sect keyword, not an ability: nothing in `engine/` or
`cards/` currently reads an "is Anarch"/sect flag off a crypt vampire for
any rules effect (`engine/cards.py::CryptCard.sect`'s own docstring: "sect
not modeled for this instance ... a card gating on sect must treat `None`
as 'does not qualify,' never guess a default sect" -- and no card in the
currently-implemented pool, `src/vtesbot/cards/__init__.py`, gates on sect
at all). No card currently in the active 2P pool or this suggested decklist
cares about controlling/being an Anarch vampire (checked against every
other crypt card in `data/decks/vekn-2p/brujah.json` and every implemented
library card's own module); there is accordingly no hypothetical
interaction to model here, per this task's own instruction not to invent
handling for an interaction nothing in the pool needs yet.

There is nothing left for this module to implement beyond registering the
card: no title, no vote value, no combat bonus, no reaction, no modifier of
any kind -- this module exists only so Octane has an effect module +
registry entry per CLAUDE.md SS6.
"""

from vtesbot.cards.registry import CardRegistration, Status, register

KRCG_ID = 201609

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Octane",
        status=Status.IMPLEMENTED,
        hooks=(),
        source=__name__,
    )
)
