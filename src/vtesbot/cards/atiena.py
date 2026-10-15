"""Atiena (crypt vampire ability). krcg id 201579.

Printed text (fetched via krcg's live API, `https://api.krcg.org/card/201579`,
2026-10-11; raw snapshot `data/cards/201579.json`, cross-checked against the
installed `krcg` package's own `krcg.vtes.VTES[201579].to_json()["card_text"]`
/ `krcg.vtes.VTES[201579].text`, same wording): "Anarch Baron of Mombasa."

Rulings: none on file (`krcg.vtes.VTES[201579].rulings == []` and the raw API
snapshot's own `"rulings": []`, both checked 2026-10-11).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Brujah, title "Baron"
(the live API's own `"title": "Baron"` field, confirmed), group 6, capacity
6, disciplines `["obf", "pot", "pre", "CEL"]`. Legal since 2021-12-31;
confirmed on the active 2P allowed list (`data/formats/2p/2026-10-03.json`)
and in the suggested 2P decklist `data/decks/vekn-2p/brujah.json` (2 copies).

Unlike Valeriya Zinovieva (201614, "Anarch Baron of Moscow: +1 strength"),
this printed text has exactly one clause, the title itself -- no colon, no
extra ability text. "Anarch Baron of Mombasa." names the title this
vampire carries -- `CryptCard.title == "Baron"`, matching
`engine/politics.py::TITLE_VOTES`'s own parsing convention ("Camarilla
Prince of London" -> title='Prince'). The vote value a ready Baron
contributes (2, Rulebook §4 Politics > Gaining Votes) is already handled
generically by `TITLE_VOTES` (`{"Baron": 2, ...}`) for every titled
vampire regardless of sect preamble -- that dict has a single plain
"Baron" key, and nothing in `engine/`/`cards/` reads sect off a titled
vampire to vary the vote value.

There is accordingly nothing left for this module to implement beyond
registering the card -- it exists only so Atiena has an effect module +
registry entry per CLAUDE.md §6, proving via test that this vampire's
title is read by the generic title-vote machinery.
"""

from vtesbot.cards.registry import CardRegistration, Status, register

KRCG_ID = 201579

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Atiena",
        status=Status.IMPLEMENTED,
        hooks=(),
        source=__name__,
    )
)
