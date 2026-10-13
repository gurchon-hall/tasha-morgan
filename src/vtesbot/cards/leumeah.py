"""Leumeah (crypt vampire ability). krcg id 201526.

Printed text (fetched via krcg's live API, `https://api.krcg.org/card/201526`,
2026-10-11; raw snapshot `data/cards/201526.json`, cross-checked against the
installed `krcg` package's own `krcg.vtes.VTES[201526].to_json()["card_text"]`
/ `krcg.vtes.VTES[201526].text`, same wording): "Anarch Baron of Canberra."

Rulings: none on file (`krcg.vtes.VTES[201526].rulings == []` and the raw API
snapshot's own `"rulings": []`, both checked 2026-10-11).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Brujah, title "Baron"
(the live API's own `"title": "Baron"` field, confirmed), group 6, capacity
6, disciplines `["cel", "for", "pot", "PRE"]`. Legal since 2019-10-05;
confirmed on the active 2P allowed list (`data/formats/2p/2026-10-03.json`)
and in the suggested 2P decklist `data/decks/vekn-2p/brujah.json` (2 copies).

Same shape as Atiena (201579, `src/vtesbot/cards/atiena.py`): a single
clause, the title itself -- no colon, no second sentence, no extra ability
text. "Anarch Baron of Canberra." names the title this specific printed
vampire carries -- `CryptCard.title == "Baron"` (confirmed above). The vote
value a ready Baron contributes (2, Rulebook SS4 Politics > Gaining Votes)
is handled generically by `engine/politics.py::TITLE_VOTES` (`{"Baron": 2,
...}`) for every titled vampire regardless of sect preamble, so no
sect-dependent vote-value question is open here.

There is accordingly nothing left for this module to implement beyond
registering the card: no combat bonus, no reaction, no modifier of any kind
-- this module exists only so Leumeah has an effect module + registry entry
per CLAUDE.md SS6, proving via test that this specific printed vampire's
title really is read by the generic title-vote machinery.
"""

from vtesbot.cards.registry import CardRegistration, Status, register

KRCG_ID = 201526

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Leumeah",
        status=Status.IMPLEMENTED,
        hooks=(),
        source=__name__,
    )
)
