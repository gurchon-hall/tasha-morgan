"""Mkhokheli (crypt vampire ability). krcg id 201561.

Printed text (verbatim, via the installed `krcg` package's `krcg.load()
[201561].text`, re-verified live 2026-10-13, matching the raw snapshot
`data/cards/201561.json`): "Camarilla Prince of Cape Town." No rulings on
file (`krcg.load()[201561].rulings == []`).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Toreador, title
"Prince", group G6, capacity 6, disciplines `["aus", "cel", "for", "PRE"]`.

Same shape as Leumeah (201526, `src/vtesbot/cards/leumeah.py`) and Atiena
(201579, `src/vtesbot/cards/atiena.py`): a single clause, the title itself
-- no colon, no second sentence, no extra ability text. "Camarilla Prince of
Cape Town." names the title this specific printed vampire carries --
`CryptCard.title == "Prince"` (confirmed above). The vote value a ready
Prince contributes (2, Rulebook SS4 Politics > Gaining Votes) is handled
generically by `engine/politics.py::TITLE_VOTES` (`{"Prince": 2, ...}`) for
every titled vampire regardless of sect preamble, so no sect-dependent
vote-value question is open here.

There is accordingly nothing left for this module to implement beyond
registering the card: no combat bonus, no reaction, no modifier of any kind
-- this module exists only so Mkhokheli has an effect module + registry
entry per CLAUDE.md SS6, proving via test that this specific printed
vampire's title really is read by the generic title-vote machinery.
"""

from vtesbot.cards.registry import CardRegistration, Status, register

KRCG_ID = 201561

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Mkhokheli",
        status=Status.IMPLEMENTED,
        hooks=(),
        source=__name__,
    )
)
