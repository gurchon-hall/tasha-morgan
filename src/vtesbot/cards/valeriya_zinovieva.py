"""Valeriya Zinovieva (crypt vampire ability). krcg id 201614.

Printed text (fetched via krcg's live API, `https://api.krcg.org/card/201614`,
2026-10-11; raw snapshot `data/cards/201614.json`, cross-checked against the
installed `krcg` package's own `krcg.vtes.VTES[201614].to_json()["card_text"]`,
same wording): "Anarch Baron of Moscow: +1 strength."

Rulings: none on file (`krcg.vtes.VTES[201614].rulings == []` and the raw API
snapshot's own `"rulings": []`, both checked 2026-10-11).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Brujah, title "Baron",
group 6, capacity 7, disciplines `["cel", "pre", "pro", "POT"]`. Legal since
2021-12-31; confirmed on the active 2P allowed list (`data/formats/2p/
2026-10-03.json`) and in the suggested 2P decklist `data/decks/vekn-2p/
brujah.json` (3 copies, tied for the deck's highest crypt count alongside
Saku Pihlajamäki).

Two distinct components, exactly like Marcos Belegrad's and Modius's own
"<title>: <ability text>" printed-text shape (`src/vtesbot/cards/
marcos_belegrad.py`, `src/vtesbot/cards/modius.py`):

1. "Anarch Baron of Moscow" names the title this specific printed vampire
   carries -- `CryptCard.title == "Baron"` (confirmed above). The vote value
   a ready Baron contributes (2, Rulebook SS4 Politics > Gaining Votes:
   "2 votes for each ready prince or baron") is already handled generically
   by `engine/politics.py::TITLE_VOTES` (`{"Baron": 2, ...}`) for *every*
   titled vampire, Valeriya included -- no card-specific code is needed, or
   added, for that part (same reasoning `marcos_belegrad.py`'s own module
   docstring gives for why it only adds Marcos's own reaction *on top of*
   the generic title-vote machinery, not the title-vote machinery itself).
2. "+1 strength" is this card's own distinct, unconditional effect -- the
   only part this module implements.

Timing window / shape: a flat, always-true combat bonus, not a choice a
Methuselah elects to apply or withhold turn to turn (CLAUDE.md rule 3's
"mandatory effects defined by the rules" exception) -- exactly the kind of
printed vampire ability `engine/combat.py`'s own module docstring names as
the motivating case for `"combat_strength_modifier"` ("a passive, mandatory
numeric hook ... for printed vampire abilities that are not a choice, e.g. a
flat '+1 strength' line"): `Hook.COMBAT_STRENGTH_MODIFIER`/
`COMBAT_STRENGTH_MODIFIER_HOOK`, summed via `hooks.sum_modifiers` into every
hand-strike (and card-strike, via `_base_hand_strike_damage`-style reads,
e.g. `dust_up.py`) damage computation for this vampire's own strikes. No new
engine hook wiring is needed: this is the hook's first production provider,
but the call site (`engine/combat.py::_strike_strength`) and the generic
`sum_modifiers` contract were already wired and tested (milestone-3
scaffolding pass, `tests/rules/test_combat.py`,
`tests/cards/test_dust_up.py::test_ani_damage_stacks_with_a_live_strength_
modifier`) before this card existed.

Target/scope: "+1 strength" is Valeriya's own strength, affecting only *her
own* strikes (the controller's combatant in the current matchup), never the
opponent's -- the provider below checks that the specific vampire named by
`context["vampire"]` (the striking combatant, per `_strike_strength`'s own
`vampire=vampire.instance_id` call-site convention) is controlled by
`context["player"]` and is this exact printed card (`krcg_id == KRCG_ID`); it
is not merely "any Baron" or "any Brujah" (unlike e.g. a hypothetical clan-
conditional bonus) and never contributes anything for the opponent's side of
the same strike. No zone (`ready`/`torpor`) gate is added: `"combat_strength_
modifier"` is only ever read for a vampire that is actually a live combatant
in a resolving strike (`engine/combat.py::_strike_strength`/`_ask_strike`'s
own call sites), and a torpid vampire cannot be in combat at all, so an
explicit zone check here would be dead code, not a missing safeguard.

Duration: for as long as this specific vampire is in play and striking --
no "until end of combat"/"this round only" qualifier in the text, unlike a
played card's temporary effect; this matches the hook's own "passive,
mandatory" nature (no activation, no expiry to track).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.combat import COMBAT_STRENGTH_MODIFIER_HOOK
from vtesbot.engine.state import GameState

KRCG_ID = 201614


def _provide_valeriya_zinovieva(state: GameState, context: Mapping[str, Any]) -> int:
    player = context.get("player")
    vampire_id = context.get("vampire")
    if player is None or vampire_id is None:
        return 0
    vampire = state.players[player].vampires.get(vampire_id)
    if vampire is None or vampire.card.krcg_id != KRCG_ID:
        return 0
    return 1


hooks.register(COMBAT_STRENGTH_MODIFIER_HOOK, _provide_valeriya_zinovieva)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Valeriya Zinovieva",
        status=Status.IMPLEMENTED,
        hooks=(Hook.COMBAT_STRENGTH_MODIFIER,),
        source=__name__,
    )
)
