"""Kevin Jackson (crypt vampire ability). krcg id 201629.

Printed text (verbatim, via the installed `krcg` package's `krcg.vtes.VTES
[201629].card_text`, re-verified live 2026-10-14, matching the raw API
endpoint `https://api.krcg.org/card/201629`, snapshot saved to
`data/cards/201629.json`): "Camarilla Prince of Chicago: Kevin gets +1
strength in combat with a Brujah. Brujah get +1 strength in combat with
him."

Rulings: none on file (`krcg.vtes.VTES[201629].rulings == []`, checked
2026-10-14).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Ventrue, title
"Prince", group 7, capacity 7, disciplines `("dom", "for", "pre")`
(lowercase-only per krcg -- no superior level printed). Legal since
2022-05-17 (the raw snapshot's own `"legal"` field -- New Blood's own
release date, 2022-04-17, is a different field and not this card's legality
date); confirmed on the active 2P allowed list (`data/formats/2p/
2026-10-03.json`) and in the suggested 2P decklist `data/decks/vekn-2p/
ventrue.json` (1 copy).

Two components:

1. "Camarilla Prince of Chicago" names the title this specific printed
   vampire carries -- `CryptCard.title == "Prince"` (confirmed above). The
   vote value a ready Prince contributes (2, Rulebook §4 Politics > Gaining
   Votes) is already handled generically by `engine/politics.py::
   TITLE_VOTES` (`{"Prince": 2, ...}`) for every titled vampire -- no
   card-specific code is needed, or added, for that part (same reasoning as
   every other titled-vampire-only module in this pool, e.g. `cards/
   mkhokheli.py`).
2. The two-sentence combat clause is this card's own distinct effect, a
   symmetric clan-conditional strength bonus: Kevin's own strikes against a
   Brujah opponent get +1 strength, *and* a Brujah's own strikes against
   Kevin get +1 strength -- two independent one-directional grants, not a
   single mutual "+1 to whoever fights the other," since each sentence
   names only one side of the matchup as the beneficiary.

Timing window / shape: a flat, always-true combat bonus whenever the
matchup condition holds, not a choice a Methuselah elects to apply or
withhold (CLAUDE.md rule 3's "mandatory effects defined by the rules"
exception, same as Valeriya Zinovieva's own unconditional "+1 strength",
`src/vtesbot/cards/valeriya_zinovieva.py`) -- summed via
`engine/combat.py::COMBAT_STRENGTH_MODIFIER_HOOK`/`hooks.sum_modifiers` into
every strike damage computation for the matching combatant. No new engine
hook wiring is needed: `hand_strike_damage`'s existing call already passes
`opponent` (the live strike's other combatant's id) alongside `player`/
`vampire`, which this card's own clan-conditional check needs and no
previously-implemented `combat_strength_modifier` provider has read before.

Target/scope: looked up via `state.other_player(context["player"])` to find
the opponent's own `VampireInPlay` -- justified by RUL-001's own settled
reading: with exactly two
Methuselahs, combat is always strictly between the two players' own
vampires, so the strike's `context["opponent"]` always belongs to whichever
player is not `context["player"]`. Clause 1 is gated on `vampire.card.
krcg_id == KRCG_ID` (this exact printed Kevin, not merely "any Ventrue
Prince") and `opponent.card.clan == "Brujah"`; clause 2 is gated on
`vampire.card.clan == "Brujah"` and `opponent.card.krcg_id == KRCG_ID` --
mirroring Valeriya Zinovieva's own precedent of gating identity on
`krcg_id`, never on title/clan alone. The two checks are mutually exclusive
in any real matchup (a vampire cannot simultaneously be Kevin and a
different printed Brujah card) and are summed, not short-circuited, so a
future synthetic test exercising both conditions on the same call still
gets the correct additive answer.

Duration: for as long as Kevin or the Brujah combatant is in play and
striking in this exact matchup -- no "until end of combat"/"this round
only" qualifier in the text, matching the hook's own passive, mandatory
nature (no activation, no expiry to track).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.combat import COMBAT_STRENGTH_MODIFIER_HOOK
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 201629
BRUJAH = "Brujah"


def _combatants(
    state: GameState, context: Mapping[str, Any]
) -> tuple[VampireInPlay | None, VampireInPlay | None]:
    """The striking vampire and its opponent for this `combat_strength_modifier`
    offer -- `context["opponent"]` always belongs to `state.other_player
    (context["player"])` (see module docstring, RUL-001)."""
    player = context.get("player")
    vampire_id = context.get("vampire")
    opponent_id = context.get("opponent")
    if player is None or vampire_id is None or opponent_id is None:
        return None, None
    vampire = state.players[player].vampires.get(vampire_id)
    opponent = state.players[state.other_player(player)].vampires.get(opponent_id)
    return vampire, opponent


def _provide_kevin_jackson(state: GameState, context: Mapping[str, Any]) -> int:
    vampire, opponent = _combatants(state, context)
    if vampire is None or opponent is None:
        return 0
    bonus = 0
    if vampire.card.krcg_id == KRCG_ID and opponent.card.clan == BRUJAH:
        bonus += 1
    if vampire.card.clan == BRUJAH and opponent.card.krcg_id == KRCG_ID:
        bonus += 1
    return bonus


hooks.register(COMBAT_STRENGTH_MODIFIER_HOOK, _provide_kevin_jackson)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Kevin Jackson",
        status=Status.IMPLEMENTED,
        hooks=(Hook.COMBAT_STRENGTH_MODIFIER,),
        source=__name__,
    )
)
