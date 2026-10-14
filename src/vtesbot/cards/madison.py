"""Madison (crypt vampire ability). krcg id 201557.

Printed text (verbatim, via the installed `krcg` package's `krcg.vtes.VTES
[201557].card_text`, re-verified live 2026-10-14, matching the raw API
endpoint `https://api.krcg.org/card/201557`, snapshot saved to
`data/cards/201557.json`): "Camarilla." No rulings on file (`krcg.vtes.VTES
[201557].rulings == []`).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Ventrue, group 6,
capacity 6, disciplines `("dom", "for", "pre")`. The live API's own
`"title"` field is `null`/`None` -- unlike Mkhokheli/Horst von Bruhl,
Madison carries no title at all, just the bare sect keyword "Camarilla."
with no city, no colon, no second sentence. Legal since 2020-12-30 (the raw
snapshot's own `"legal"` field -- Fifth Edition's own release date,
2020-11-30, is a different field and not this card's legality date);
confirmed on the active 2P allowed list (`data/formats/2p/2026-10-03.json`)
and in the suggested 2P decklist `data/decks/vekn-2p/ventrue.json` (1
copy).

Same shape as Octane (201609, `src/vtesbot/cards/octane.py`) and Siarhei
Levchenko: "Camarilla." is a sect keyword, not an ability. Nothing in
`engine/` or `cards/` currently reads an "is Camarilla"/sect flag off a
crypt vampire for any rules effect of Madison's own (`engine/cards.py::
CryptCard.sect`'s own docstring: "sect not modeled for this instance ... a
card gating on sect must treat `None` as 'does not qualify,' never guess a
default sect"). No card currently in the active 2P pool or this suggested
decklist cares about controlling/being a Camarilla vampire as such (checked
against every other crypt card in `data/decks/vekn-2p/ventrue.json` and
every implemented library card's own module); there is accordingly no
hypothetical interaction to model here, per this task's own instruction not
to invent handling for an interaction nothing in the pool needs yet.

There is nothing left for this module to implement beyond registering the
card: no title, no vote value, no combat bonus, no reaction, no modifier of
any kind -- this module exists only so Madison has an effect module +
registry entry per CLAUDE.md SS6.
"""

from vtesbot.cards.registry import CardRegistration, Status, register

KRCG_ID = 201557

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Madison",
        status=Status.IMPLEMENTED,
        hooks=(),
        source=__name__,
    )
)
