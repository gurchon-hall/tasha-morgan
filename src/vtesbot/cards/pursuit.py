"""Pursuit (Combat). krcg id 101523.

Card text (verbatim, via the installed `krcg` 5.14+ package's own
`krcg.vtes.VTES["Pursuit"].card_text`, 2026-10-12, matching the raw snapshot
saved to `data/cards/101523.json` byte-for-byte, cross-checked live against
`https://api.krcg.org/card/101523`):
    "[cel] Maneuver.
    [CEL] Additional strike (limited)."

Rulings: none on file -- `rulings == []`, both via the installed `krcg`
package and the live API (re-checked 2026-10-12).

Card type: Combat (`types == ["Combat"]`). `discipline_requirement ==
{"type": "Mono", "disciplines": ["cel"]}` -- a single discipline, Celerity,
printed at two different levels (same shape as Side Strike,
`src/vtesbot/cards/side_strike.py`: Rulebook §3 "Discipline symbol within a
diamond ... may opt to use either the basic (plain text) or the superior
(bold) effect ... but not both"). `clan_requirement == []`,
`path_requirement == []`, `cost is None`, `burn_option is False`,
`trifle is False`. Legal since 1996-11-27; confirmed on the active 2P
allowed list (`data/formats/2p/2026-10-03.json`, krcg id 101523) and in the
suggested 2P decklists `data/decks/vekn-2p/brujah.json` (3 copies) and
`data/decks/vekn-2p/toreador.json` (2 copies), 5 total.

No Ⓓ marker, no prey/predator/"other Methuselahs" wording, no political
vote -- this is a plain Combat card played during an already-resolving
combat, so OQ-1 (CLAUDE.md §3) does not apply.

Whether Pursuit's basic "Maneuver." clause carries Rulebook §4's "cannot
use a second strike card or weapon to maneuver again"/"cannot choose any
other strike" restrictions (OQ-27, resolved): §4 Combat > Choose Strike
(`data/sources/rulebook/2026-10-09/4-detailed-turn-sequence.md:824-828`):
"Each minion chooses their strike. ... If a minion has used a maneuver
from a strike (either a strike card or a weapon) this round, then they
cannot choose any other strike for their initial strike of the round."
This pins down the test: the maneuver must itself be **from a strike** --
the same clause that grants the maneuver must also be, or be part of, a
strike effect (contrast Slam's "[POT] As above, with 1 optional
maneuver..." and .44 Magnum's "Strike: 2R damage, with 1 optional
maneuver...", where the maneuver is printed inside the strike clause).
Pursuit's basic clause is a bare "Maneuver." with no "Strike:" wording and
no "as above" link to the card's own separate, differently-gated superior
"Additional strike (limited)" clause -- it is not "a maneuver from a
strike" in the Rulebook's technical sense, exactly as Dance with the
Devil's identically bare "[obf] or [tha] Maneuver, only usable to get to
close range" (krcg id 102315) is not either. Neither §4 restriction is
therefore triggered by playing Pursuit's basic clause: it is a plain
maneuver, the same category as a vampire's own innate maneuver-granting
title ability (Saku Pihlajamäki's "1 optional maneuver each combat") or
Dance with the Devil's clauses, not a strike-card-bundled one (Slam, .44
Magnum -- still correctly left unbuilt, per `engine/combat.py`'s own
"Determine Range and maneuvers" docstring section).

"[cel] Maneuver." (basic clause): a plain `MANEUVER_HOOK` grant, offered at
either Celerity level (Rulebook §3: superior unlocks either effect), the
same hook Saku Pihlajamäki's own innate ability uses -- the only difference
being this is a played *card* (consumed via `play_from_hand`), so no
per-combat "already used" bookkeeping is needed: each physical copy is its
own one-shot grant. Not marked "optional" on the card (unlike Fleetness's/
Saku's "1 optional maneuver"), but with no engine consequence: the
existing choice already includes "do not maneuver" unconditionally
(`_ask_maneuver`'s own `hooks.PASS_VALUE` option) -- a player simply does
not play this card if they do not want its maneuver.

"[CEL] Additional strike (limited)." (superior clause): the same shape as
Side Strike's own superior clause -- a plain `COMBAT_ADDITIONAL_STRIKE_HOOK`
grant, gated on superior `"CEL"` and the cross-card "(limited)" cap
(`additional_strike_limit_used`/`mark_additional_strike_limit_used`,
OQ-19). Entirely independent of the basic clause: a superior-Celerity
vampire holding two physical copies could maneuver with one and claim the
additional strike with the other in the same round.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.combat import (
    COMBAT_ADDITIONAL_STRIKE_HOOK,
    MANEUVER_HOOK,
    additional_strike_limit_used,
    mark_additional_strike_limit_used,
)
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101523
CEL_BASIC = "cel"
CEL_SUPERIOR = "CEL"
CARD_TYPE = "Combat"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): matches
this module's own "Card type: Combat" docstring fact above."""


def _controllers_vampire(state: GameState, context: Mapping[str, Any]) -> VampireInPlay | None:
    """The vampire whose own maneuver/additional-strike choice this hook
    offer is for -- both `MANEUVER_HOOK` (`_ask_maneuver`) and
    `COMBAT_ADDITIONAL_STRIKE_HOOK` (`_ask_additional_strike`) always offer
    `player=<that vampire's own controller>, vampire=<that vampire's own
    instance id>`, the same convention `side_strike.py` already relies on."""
    return state.players[context["player"]].vampires.get(context["vampire"])


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _provide_maneuver(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[cel] Maneuver." -- a plain maneuver grant at either Celerity level,
    not "from a strike" (module docstring's OQ-27 resolution), so it carries
    none of Rulebook §4's strike-lock/"second strike card" restrictions."""
    vampire = _controllers_vampire(state, context)
    if vampire is None:
        return []
    disciplines = vampire.card.disciplines
    if CEL_BASIC not in disciplines and CEL_SUPERIOR not in disciplines:
        return []
    player = context["player"]
    if not _has_card_in_hand(state, player):
        return []

    def _apply(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)

    return [
        HookOption(
            choice=Choice("pursuit:maneuver", "Pursuit [cel]: Maneuver"),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


def _provide_additional_strike(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[CEL] Additional strike (limited)." -- requires superior Celerity
    only; independent of the basic clause (module docstring)."""
    vampire = _controllers_vampire(state, context)
    if vampire is None:
        return []
    disciplines = vampire.card.disciplines
    if CEL_SUPERIOR not in disciplines:
        return []
    player = context["player"]
    if not _has_card_in_hand(state, player):
        return []
    if additional_strike_limit_used(context):
        return []  # "(limited)": a grant (this card's or another's) was already used this round.

    def _apply(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        mark_additional_strike_limit_used(context)

    return [
        HookOption(
            choice=Choice(
                "pursuit:additional_strike", "Pursuit [CEL]: Additional strike (limited)"
            ),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


hooks.register(MANEUVER_HOOK, _provide_maneuver)
hooks.register(COMBAT_ADDITIONAL_STRIKE_HOOK, _provide_additional_strike)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Pursuit",
        status=Status.IMPLEMENTED,
        hooks=(Hook.MANEUVER, Hook.COMBAT_ADDITIONAL_STRIKE),
        source=__name__,
    )
)
