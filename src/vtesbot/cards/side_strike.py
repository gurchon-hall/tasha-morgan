"""Side Strike (Combat). krcg id 101778.

Card text (verbatim, via the installed `krcg` 5.14 package's own
`krcg.loader.load_online()` result and cross-checked live against
`https://api.krcg.org/card/101778`, 2026-10-10; both match the raw snapshot
saved to `data/cards/101778.json`):
    "[cel] Strike: dodge.
    [CEL] Additional strike (limited)."

Rulings: none on file -- `rulings == []`, both via the installed `krcg`
package and the live API (checked 2026-10-10).

Card type: Combat (`types == ["Combat"]`). `discipline_requirement ==
{"type": "Mono", "disciplines": ["cel"]}` -- a single discipline, Celerity,
printed at two different levels (unlike Dust Up's three-way *choice* of
different disciplines, both clauses here key off the same `"cel"`/`"CEL"`
presence check, Rulebook §3 "Discipline symbol within a diamond ... may
opt to use either the basic (plain text) or the superior (bold) effect ...
but not both"). `clan_requirement == []`, `path_requirement == []`,
`cost is None`, `burn_option is False`, `trifle is False`. Legal since
1996-11-27; confirmed on the active 2P allowed list
(`data/formats/2p/2026-10-03.json`) and in the suggested 2P decklists
`data/decks/vekn-2p/brujah.json` (2 copies) and
`data/decks/vekn-2p/toreador.json` (4 copies), 6 total.

Unlike Dust Up's `[cel]` clause ("Strike: dodge, with 1 additional strike
(limited)" -- one bundled choice, per its own `[ANK 20220204]` ruling,
never separable), Side Strike prints its dodge and its additional strike
as two separate lines at two separate discipline levels: `[cel]`
(inferior) grants only a dodge strike; `[CEL]` (superior) grants only a
(limited) additional strike, with no dodge attached and no requirement
that the dodge be played first, or at all. A superior-Celerity vampire is
eligible for *both* clauses (Rulebook §3 "may opt to use either effect";
same convention as `bonding.py`'s two clauses), but each is an
*independent* choice offered at its own hook point (dodge at the strike
step via `COMBAT_DODGE_OPTION_HOOK`, additional strike via
`COMBAT_ADDITIONAL_STRIKE_HOOK`): playing one does not grant or consume
anything toward the other. Modeled as two independent hook providers, each
playing its own physical copy when chosen -- nothing ties the two clauses'
cards together the way Dust Up's single bundled line does.

"[cel] Strike: dodge." (inferior clause): a plain `"combat_dodge_option"`
provider, gated on basic-or-superior `"cel"`/`"CEL"` and the card being in
hand. Carries no "(limited)" restriction of its own -- the text does not
print the word, and nothing in §4 Combat caps repeated non-"(limited)"
strike/dodge options (Rulebook §2's "action modifier" cap does not apply
here: this is a combat card at the strike step, not an action modifier).

"[CEL] Additional strike (limited)." (superior clause): a plain
`"combat_additional_strike"` provider, gated on superior `"CEL"` only
(Rulebook §3: the superior effect is not available at the basic level);
using it grants one additional strike through the engine's own full
strike-choice machinery, exactly like Dust Up's own `[cel]`-granted
additional strike.

"(limited)" (§8 glossary: "A minion cannot use more than one card or
effect to gain additional strikes per round of combat"): tracked via
`engine/combat.py`'s shared, round-scoped
`additional_strike_limit_used`/`mark_additional_strike_limit_used` helpers
(ENG-013), the same mechanism `dust_up.py`'s `[cel]` clause uses. Because the
flag lives in the shared, round-scoped `round_state` dict `run_combat`
threads into both hooks' context (reset fresh every round, not per-card),
this correctly pools *across* different cards -- a vampire holding both
Dust Up and Side Strike cannot use both cards' "(limited)" grants in the
same round. The `[cel]` dodge clause carries no such check (the
restriction is printed only on the `[CEL]` additional-strike line).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.combat import (
    COMBAT_ADDITIONAL_STRIKE_HOOK,
    COMBAT_DODGE_OPTION_HOOK,
    additional_strike_limit_used,
    mark_additional_strike_limit_used,
)
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101778
CEL_BASIC = "cel"
CEL_SUPERIOR = "CEL"
CARD_TYPE = "Combat"
"""`HookOption.played_card_type` (ENG-023): matches
this module's own "Card type: Combat" docstring fact above."""


def _controllers_vampire(state: GameState, context: Mapping[str, Any]) -> VampireInPlay | None:
    """The vampire whose own dodge/additional-strike choice this hook offer
    is for -- `context["player"]` is always that vampire's own controller
    (see `engine/combat.py::_ask_strike`/`_ask_additional_strike` call
    sites: `hooks.offer(HOOK, state, player=player, vampire=vampire.
    instance_id, opponent=opponent.instance_id)`)."""
    return state.players[context["player"]].vampires.get(context["vampire"])


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _provide_dodge(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[cel] Strike: dodge." -- plain dodge, available at basic-or-superior
    Celerity, independent of the `[CEL]` additional-strike clause (see
    module docstring)."""
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
            choice=Choice("side_strike:dodge", "Side Strike [cel]: dodge"),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


def _provide_additional_strike(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[CEL] Additional strike (limited)." -- requires superior Celerity
    only; using it grants one additional strike through the engine's own
    full strike-choice machinery. Unlike Dust Up's `[cel]` clause, this
    provider *is* the `COMBAT_ADDITIONAL_STRIKE_HOOK` offer itself (there is
    no separate dodge-bundled "grant" step to record and later claim), so
    the cross-card "(limited)" cap (see module docstring) is gated and
    recorded directly here: `additional_strike_limit_used(context)` must be
    False to offer this choice at all, and choosing it immediately calls
    `mark_additional_strike_limit_used(context)`."""
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
                "side_strike:additional_strike", "Side Strike [CEL]: additional strike (limited)"
            ),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


hooks.register(COMBAT_DODGE_OPTION_HOOK, _provide_dodge)
hooks.register(COMBAT_ADDITIONAL_STRIKE_HOOK, _provide_additional_strike)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Side Strike",
        status=Status.IMPLEMENTED,
        hooks=(
            Hook.COMBAT_DODGE_OPTION,
            Hook.COMBAT_ADDITIONAL_STRIKE,
        ),
        source=__name__,
    )
)
