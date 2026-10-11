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

Unlike Valeriya Zinovieva (201614, "Anarch Baron of Moscow: +1 strength",
`src/vtesbot/cards/valeriya_zinovieva.py`), this printed text has exactly one
clause, the title itself -- no colon, no second sentence, no extra ability
text of any kind. "Anarch Baron of Mombasa." names the title this specific
printed vampire carries -- `CryptCard.title == "Baron"` (confirmed above,
matching the generic convention `engine/politics.py::TITLE_VOTES`'s own
docstring describes: "the capitalized title keyword as it appears in the
vampire's own printed text, e.g. 'Camarilla Prince of London' ->
title='Prince'" -- "Anarch Baron of Mombasa" parses the exact same way,
title='Baron'). The vote value a ready Baron contributes (2, Rulebook SS4
Politics > Gaining Votes: "2 votes for each ready prince or baron") is
already handled generically by `engine/politics.py::TITLE_VOTES`
(`{"Baron": 2, ...}`) for *every* titled vampire regardless of sect preamble
-- that dict has a single plain "Baron" key, not separate "Anarch Baron" and
"Camarilla Baron" keys, and nothing in `engine/` or `cards/` currently reads
a sect ("Anarch" vs "Camarilla") off a titled vampire to vary the vote
value, so there is no sect-dependent vote-value question left open here.

There is accordingly nothing left for this module to implement beyond
registering the card: no combat bonus, no reaction, no modifier of any kind
-- this module exists only so Atiena has an effect module + registry entry
per CLAUDE.md SS6 ("a card is implemented only when: effect code + test(s)
... + registry entry + listed in the active 2P list"), proving via test that
this specific printed vampire's title really is read by the generic
title-vote machinery (same end-to-end proof `valeriya_zinovieva.py`'s own
test file gives for its title half).
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
