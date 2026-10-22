"""Saku Pihlajamäki (crypt vampire ability). krcg id 201658.

Printed text (fetched via krcg's live API, `https://api.krcg.org/card/201658`,
2026-10-11; raw snapshot cross-checked against the installed `krcg` package's
own `krcg.vtes.VTES[201658].to_json()["card_text"]`, same wording): "Anarch
Baron of Helsinki: Saku gets 1 optional maneuver each combat."

Rulings: none on file (`krcg.vtes.VTES[201658].rulings == []`, checked
2026-10-11).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Brujah, title "Baron"
(the live API's own `"title": "Baron"` field, confirmed), group 6, capacity
8, disciplines `["for", "pro", "CEL", "POT", "PRE"]`. Legal since 2022-08-01;
confirmed on the active 2P allowed list (`data/formats/2p/2026-10-03.json`)
and in the suggested 2P decklist `data/decks/vekn-2p/brujah.json` (3 copies,
tied with Valeriya Zinovieva for the deck's highest crypt count).

Two distinct components, exactly like Valeriya Zinovieva's own
"<title>: <ability text>" printed-text shape (`src/vtesbot/cards/
valeriya_zinovieva.py`):

1. "Anarch Baron of Helsinki" names the title this specific printed vampire
   carries -- `CryptCard.title == "Baron"` (confirmed above). The vote value
   a ready Baron contributes (2, Rulebook §4 Politics > Gaining Votes: "2
   votes for each ready prince or baron") is already handled generically by
   `engine/politics.py::TITLE_VOTES` (`{"Baron": 2, ...}`) for *every* titled
   vampire, Saku included -- no card-specific code is needed, or added, for
   that part (same reasoning `valeriya_zinovieva.py`'s own module docstring
   gives for why it only adds Valeriya's own "+1 strength" effect *on top
   of* the generic title-vote machinery, not the title-vote machinery
   itself).
2. "Saku gets 1 optional maneuver each combat" is this card's own distinct
   effect -- the only part this module implements.

Engine support (`engine/combat.py`'s "Determine Range and maneuvers"
section): `MANEUVER_HOOK` is offered to each combatant's controller,
strictly alternating turn by turn, during the Determine Range step, before
the strike step each round. This card's provider:

- Returns one `HookOption` exactly when Saku is the combatant whose turn it
  is (gated on `context["player"]`/`context["vampire"]` naming this exact
  vampire instance, `card.krcg_id == KRCG_ID`) *and* the once-per-combat
  grant has not yet been used this combat.
- "Optional": `_ask_maneuver`/`_determine_range` always offers a decline
  choice (`hooks.PASS_VALUE`) alongside every registered option, so nothing
  here needs to encode optionality.
- "1 ... each combat" (not "each round"): `context["combat_state"]`
  (`COMBAT_STATE_CONTEXT_KEY`) is the shared dict `run_combat` creates once,
  outside its per-round loop, so a flag recorded there persists for every
  round of the same combat but resets for a fresh combat -- keyed by
  `context["vampire"]` so a future second vampire's own per-combat grant
  would never collide with Saku's.

Target/scope: the maneuver is granted to Saku specifically, never the
opponent or a different vampire of the same player. No zone gate is added
beyond what the engine already guarantees:
`MANEUVER_HOOK` is only ever offered for a vampire that is actually a live
combatant in a resolving combat (`_determine_range`'s own call sites).

Duration: for as long as this specific vampire is in play and in combat --
no further qualifier in the text beyond "each combat", implemented
directly by the per-combat scratch dict above.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.combat import MANEUVER_HOOK
from vtesbot.engine.decision import Choice
from vtesbot.engine.state import GameState

KRCG_ID = 201658

_USED_KEY = "saku_pihlajamaki_maneuver_used"


def _provide_saku_pihlajamaki(
    state: GameState, context: Mapping[str, Any]
) -> list[hooks.HookOption]:
    player = context.get("player")
    vampire_id = context.get("vampire")
    combat_state = context.get("combat_state")
    if player is None or vampire_id is None or combat_state is None:
        return []
    vampire = state.players[player].vampires.get(vampire_id)
    if vampire is None or vampire.card.krcg_id != KRCG_ID:
        return []
    used = combat_state.setdefault(_USED_KEY, set())
    if vampire_id in used:
        return []

    def use(s: GameState) -> None:
        used.add(vampire_id)

    choice = Choice("saku_pihlajamaki_maneuver", "Saku Pihlajamäki's maneuver")
    # `played_card_type` stays at its default `None` (ENG-023): this is a
    # printed crypt-vampire ability, not a library card being played at all.
    return [hooks.HookOption(choice=choice, apply=use)]


hooks.register(MANEUVER_HOOK, _provide_saku_pihlajamaki)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Saku Pihlajamäki",
        status=Status.IMPLEMENTED,
        hooks=(Hook.MANEUVER,),
        source=__name__,
    )
)
