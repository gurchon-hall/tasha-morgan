"""Horst von Bruhl (crypt vampire ability). krcg id 201550.

Printed text (verbatim, via the installed `krcg` package's `krcg.vtes.VTES
[201550].card_text`, re-verified live 2026-10-14, matching the raw API
endpoint `https://api.krcg.org/card/201550`, snapshot saved to
`data/cards/201550.json`): "Camarilla Prince of Mannheim." No rulings on
file (`krcg.vtes.VTES[201550].rulings == []`).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Ventrue, title
"Prince", group 6, capacity 6, disciplines `("aus", "dom", "pre", "FOR")`.
Legal since 2020-12-30 (the raw snapshot's own `"legal"` field -- Fifth
Edition's own release date, 2020-11-30, is a different field and not this
card's legality date); confirmed on the active 2P allowed list (`data/
formats/2p/2026-10-03.json`) and in the suggested 2P decklist `data/decks/
vekn-2p/ventrue.json` (1 copy).

Same shape as Mkhokheli (201561, `src/vtesbot/cards/mkhokheli.py`) and
Leumeah/Atiena: a single clause, the title itself -- no colon, no second
sentence, no extra ability text. "Camarilla Prince of Mannheim." names the
title this specific printed vampire carries -- `CryptCard.title == "Prince"`
(confirmed above). The vote value a ready Prince contributes (2, Rulebook
SS4 Politics > Gaining Votes) is handled generically by `engine/politics.py
::TITLE_VOTES` (`{"Prince": 2, ...}`) for every titled vampire regardless of
sect preamble, so no sect-dependent vote-value question is open here.

There is accordingly nothing left for this module to implement beyond
registering the card: no combat bonus, no reaction, no modifier of any kind
-- this module exists only so Horst von Bruhl has an effect module +
registry entry per CLAUDE.md SS6, proving via test that this specific
printed vampire's title really is read by the generic title-vote machinery.
"""

from vtesbot.cards.registry import CardRegistration, Status, register

KRCG_ID = 201550

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Horst von Brühl",
        status=Status.IMPLEMENTED,
        hooks=(),
        source=__name__,
    )
)
