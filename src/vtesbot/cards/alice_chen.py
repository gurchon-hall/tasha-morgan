"""Alice Chen (crypt vampire ability). krcg id 201531.

Printed text (fetched via the installed `krcg` package, `krcg.load()[201531]`,
2026-10-15; raw snapshot `data/cards/201531.json`): "Camarilla Prince of
Nairobi."

Rulings: none on file (`krcg.load()[201531].rulings == []`, checked
2026-10-15).

Card type: crypt vampire (`types == [Type.VAMPIRE]`). Clan Ventrue, group 6,
capacity 7, title Prince, disciplines `["dom", "obf", "FOR", "PRE"]`. Legal
on the active 2P allowed list (`data/formats/2p/2026-10-03.json`) and in the
suggested 2P decklist `data/decks/vekn-2p/ventrue.json` (2 copies).

Same shape as Siarhei Levchenko (`src/vtesbot/cards/siarhei_levchenko.py`,
itself mirroring Octane, `src/vtesbot/cards/octane.py`): a bare sect/title
keyword line, "Camarilla Prince of Nairobi.", with no colon and no second
sentence -- unlike Alexa Draper/Queen Anne/Modius, who share Alice Chen's
"Camarilla Prince of <city>" preamble but each follow it with a colon and a
mechanical clause, Alice Chen's text stops at the city name. The title's
vote value (`engine/politics.py::TITLE_VOTES["Prince"] == 2`) already
applies generically to any titled vampire casting a title vote
(`_collect_vote_sources`); nothing card-specific is needed to grant it.

There is nothing left for this module to implement beyond registering the
card: no mechanical clause, no vote-affecting text beyond the title itself,
no combat bonus, no reaction -- this module exists only so Alice Chen has an
effect module + registry entry per CLAUDE.md §6.
"""

from vtesbot.cards.registry import CardRegistration, Status, register

KRCG_ID = 201531

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Alice Chen",
        status=Status.IMPLEMENTED,
        hooks=(),
        source=__name__,
    )
)
