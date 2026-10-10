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
presence check, Rulebook SS3 "Discipline symbol within a diamond ... may
opt to use either the basic (plain text) or the superior (bold) effect ...
but not both"). `clan_requirement == []`, `path_requirement == []`,
`cost is None`, `burn_option is False`, `trifle is False`. Legal since
1996-11-27; confirmed on the active 2P allowed list
(`data/formats/2p/2026-10-03.json`) and in the suggested 2P decklists
`data/decks/vekn-2p/brujah.json` (2 copies) and
`data/decks/vekn-2p/toreador.json` (4 copies), 6 total.

Unlike Dust Up's `[cel]` clause ("Strike: dodge, with 1 additional strike
(limited)" -- one bundled choice, per its own `[ANK 20220204]` ruling, never
separable), Side Strike prints its dodge and its additional strike as two
separate lines at two separate discipline levels: `[cel]` (inferior) grants
only a dodge strike; `[CEL]` (superior) grants only a (limited) additional
strike, with no dodge attached to it and no requirement that the dodge be
played first, or at all. A vampire with superior Celerity is eligible for
*both* clauses (Rulebook SS3's own "may opt to use either effect": superior
discipline presence satisfies a basic-level discipline check too, the same
convention already used by `bonding.py`'s two clauses -- `SUPERIOR not in
disciplines` for the superior clause, `BASIC not in disciplines and
SUPERIOR not in disciplines` for the basic one) -- but each is still an
*independent* choice offered at its own hook point (dodge at the strike
step via `COMBAT_DODGE_OPTION_HOOK`, additional strike after the normal
pair via `COMBAT_ADDITIONAL_STRIKE_HOOK`): playing the additional strike
does not require having played (or being about to play) the dodge, and
playing the dodge does not grant or consume anything toward the additional
strike. Modeled as two independent hook providers, each gated on its own
discipline level and each playing (removing from hand, replacing from the
library) its own physical copy of the card when chosen -- so a vampire
holding two copies could, in principle, play the dodge from one copy and
the additional strike from a second copy, or either clause twice from two
different copies played on different rounds (subject to the additional
strike's own "(limited)" cap, below); nothing about this text ties the two
clauses' physical cards together the way Dust Up's single bundled line
does.

"[cel] Strike: dodge." (inferior clause): a plain `"combat_dodge_option"`
provider (`engine/combat.py::COMBAT_DODGE_OPTION_HOOK`), gated on basic-or-
superior `"cel"`/`"CEL"` and the card being in hand. Carries no "(limited)"
restriction of its own -- the text does not print the word, and nothing
stops a vampire from playing the dodge clause of one physical copy per
round the same way any other card is normally limited only by how many
copies are in hand (Rulebook SS2 "A minion cannot play the same action
modifier card more than once during a single action" does not apply here:
this is a combat card at the strike step, not an action modifier, and
nothing in SS4 Combat caps repeated non-"(limited)" strike/dodge options).

"[CEL] Additional strike (limited)." (superior clause): a plain
`"combat_additional_strike"` provider (`engine/combat.py::
COMBAT_ADDITIONAL_STRIKE_HOOK`), gated on superior `"CEL"` only (Rulebook
SS3: the bold/superior effect is not available at the basic level) and the
card being in hand; using it grants one additional strike claimed through
the engine's own full strike-choice machinery (`_ask_additional_strike`'s
own contract: "an additional strike is never a fixed/hardcoded hand
strike" -- `engine/combat.py` module docstring), exactly like Dust Up's own
`[cel]`-granted additional strike.

"(limited)" (SS8 glossary; `engine/combat.py` module docstring's own
general restatement of the rule this card text invokes: "A minion cannot
use more than one card or effect to gain additional strikes per round of
combat"): tracked the same way, and with the same deliberately-documented
granularity simplification, as Dust Up's own `[cel]` clause (see
`dust_up.py`'s module docstring for the full reasoning -- repeated here only
in summary, not re-derived): `engine/combat.py`'s three combat hooks carry
no round-boundary (or even combat-boundary) scratch container a hook
provider can see (confirmed by re-reading `_ask_strike`/`_resolve_strike_
pair`/`_ask_additional_strike`/`run_combat` again for this card: still true,
unchanged since Dust Up's own pass), so this module tracks the cap itself,
per *vampire instance*, for as long as that instance exists -- strictly
*more* restrictive than "once per round" (it also forbids a legitimate
replay in a later round or later combat that the rules would in fact
allow), never less. Scoped to this card's own clause only, the same
granularity Dust Up's own module uses (not pooled with any other,
hypothetical additional-strike-granting card's own separate tracking --
that cross-card pooling gap, if it ever matters, pre-exists this card and
is Dust Up's own module's gap too, not something this card introduces or is
asked to fix). Uses the identical `id(vampire)` + `weakref.finalize`
mechanism as `dust_up.py` (`VampireInPlay` is unhashable, see that module's
own docstring for the full footgun explanation) rather than importing Dust
Up's private `_CEL_BOOKKEEPING` -- a different card's own private per-card
state, keyed only by instance and not by which card played it, would be
wrong to share across two unrelated physical cards.
"""

import weakref
from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.combat import COMBAT_ADDITIONAL_STRIKE_HOOK, COMBAT_DODGE_OPTION_HOOK
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101778
CEL_BASIC = "cel"
CEL_SUPERIOR = "CEL"

ADDITIONAL_STRIKE_USED_KEY = "additional_strike_used"

# Per-vampire "(limited)" bookkeeping for the `[CEL]` additional-strike
# clause -- see module docstring for why this cannot use the shared
# `_shared.bleed_bookkeeping`/`pending` convention (no equivalent scratch
# object exists in `engine/combat.py`'s hook contexts), why the chosen
# granularity is "once per vampire instance" rather than "once per round"
# (strictly more restrictive, matching `dust_up.py`'s own precedent), and
# why this is a module-private dict rather than a shared pool with any
# other additional-strike-granting card.
#
# `VampireInPlay` (`engine/state.py`) is a plain `@dataclass` with no
# `frozen=True`/`unsafe_hash=True`, so it is unhashable and cannot be used
# as a `dict`/`WeakKeyDictionary` key directly. Keyed instead by
# `id(vampire)` in a plain module-level `dict`, paired with a
# `weakref.finalize` callback that pops the entry the instant this specific
# vampire object is garbage-collected -- this prevents the "`id()` gets
# reused after garbage-collection" footgun from leaking a stale flag into
# an unrelated, later vampire object that happens to receive the same
# `id()`.
_CEL_BOOKKEEPING: dict[int, dict[str, bool]] = {}


def _cel_book(vampire: VampireInPlay) -> dict[str, bool]:
    key = id(vampire)
    book = _CEL_BOOKKEEPING.get(key)
    if book is None:
        book = {}
        _CEL_BOOKKEEPING[key] = book
        weakref.finalize(vampire, _CEL_BOOKKEEPING.pop, key, None)
    return book


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
        )
    ]


def _provide_additional_strike(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[CEL] Additional strike (limited)." -- requires superior Celerity
    only; using it grants one additional strike through the engine's own
    full strike-choice machinery. See module docstring for the "(limited)"
    granularity this module enforces."""
    vampire = _controllers_vampire(state, context)
    if vampire is None:
        return []
    disciplines = vampire.card.disciplines
    if CEL_SUPERIOR not in disciplines:
        return []
    player = context["player"]
    if not _has_card_in_hand(state, player):
        return []
    book = _cel_book(vampire)
    if book.get(ADDITIONAL_STRIKE_USED_KEY):
        return []  # "(limited)": already played this card's [CEL] clause.

    def _apply(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        book[ADDITIONAL_STRIKE_USED_KEY] = True

    return [
        HookOption(
            choice=Choice(
                "side_strike:additional_strike", "Side Strike [CEL]: additional strike (limited)"
            ),
            apply=_apply,
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
