"""Dust Up (Combat). krcg id 100597.

Card text (verbatim, re-verified via the installed `krcg` 4.18 package's own
`VTES["Dust Up"].to_json()` and cross-checked live against
`https://api.krcg.org/card/100597`, 2026-10-10; both match the raw snapshot
saved to `data/cards/100597.json`):
    "Requires an Anarch.
    [ani] Strike: hand strike at +1 damage. This strike cannot be dodged.
    [cel] Strike: dodge, with 1 additional strike (limited).
    [pot] Strike: hand strike at +2 damage."

Rulings (verbatim, via krcg; both the installed package and the live API
agree):
    - "[ani] [pot] Additional damage inherits all of the properties of the
      base damage." [TOM 19960225]
    - "[cel] The additional strike is not optional: you cannot play it for
      the dodge only if you already played it for a (limited) additional
      strike this round." [ANK 20220204]
    - "When played, a multi-Disciplines card counts as requiring the
      Discipline(s) being used. In the hand, library, or ash heap, the card
      is considered to require any and/or all Disciplines listed on it."
      [LSJ 20011204-3] [PIB 20130704]
    - "[ani] Does not prevent the opponent from dodging, the dodge just has
      no effect." [LSJ 20030902-2] [LSJ 20060808-1]

Card type: Combat (`types == ["Combat"]`). Live API `discipline_requirement
== {"type": "Choice", "disciplines": ["ani", "cel", "pot"]}` -- any *one* of
the three, all lowercase/inferior level (confirmed by the installed
package's own `multidisc == True`, `disciplines == ["ani", "cel", "pot"]`,
no uppercase/superior variant printed). `clan_requirement == []`,
`path_requirement == []`, `cost is None`, `burn_option is False`,
`trifle is False`. Legal since 2016-02-16; confirmed on the active 2P
allowed list (`data/formats/2p/2026-10-03.json`) and in the suggested 2P
decklist `data/decks/vekn-2p/brujah.json` (6 copies).

Status: implemented (OQ-18, `docs/OPEN_QUESTIONS.md`, resolved -- both
engine gaps that previously blocked this card are closed: `Sect`/
`CryptCard.sect`/`derive_sect` in `engine/cards.py`, and the
`"combat_dodge_option"`/`"combat_additional_strike"` hooks in
`engine/combat.py`, including `StrikeDamage.ignore_dodge` for the `[ani]`
clause's dodge-proof strike).

"Requires an Anarch": a card-level legality gate independent of which
discipline clause is used (Rulebook SS6 Vampire Sects: "Some cards can only
be played by Anarch vampires."). `vampire.card.sect` is the engine's own
per-vampire sect field (OQ-18 Gap 1); every provider below first checks
`vampire.card.sect is Sect.ANARCH` and offers nothing at all otherwise --
including when `sect is None` ("not modeled for this instance": a synthetic
test vampire that was never run through `derive_sect`, or a real vampire the
not-yet-built deck-import pipeline has not populated -- `CryptCard`'s own
docstring: "a card gating on sect must treat `None` as 'does not qualify,'
never guess a default sect").

"[ani] Strike: hand strike at +1 damage. This strike cannot be dodged." /
"[pot] Strike: hand strike at +2 damage.": both are plain `"combat_strike_
option"` providers (`engine/combat.py::COMBAT_STRIKE_OPTION_HOOK`), gated on
basic-or-superior `"ani"`/`"pot"` (no superior variant is printed on this
card itself, but a vampire who separately has superior Animalism/Potence
still has basic, same `"dom"`/`"DOM"` presence check already used by
`threats.py`/`bonding.py`). "+1"/"+2 damage" is computed relative to
whatever a plain hand strike would otherwise deal right now -- `engine/
combat.py::HAND_STRIKE_STRENGTH` plus any live `"combat_strength_modifier"`
contribution (`hooks.sum_modifiers`), the exact same computation
`_strike_strength` performs internally -- rather than a hardcoded "1", so
the ruling "[ani] [pot] Additional damage inherits all of the properties of
the base damage" (i.e. it stacks with, rather than replaces, any other
strength bonus already in play) holds structurally, not by coincidence.
`[ani]`'s strike is additionally flagged `StrikeDamage(ignore_dodge=True)`:
per the Golden Rule for Cards (CLAUDE.md SS2 / Rulebook SS3) and this card's
own ruling ("Does not prevent the opponent from dodging, the dodge just has
no effect" [LSJ 20030902-2] [LSJ 20060808-1]), the opponent may still choose
to dodge (a real, legal choice, handled generically by `engine/combat.py`'s
own dodge machinery), but that dodge has zero effect against this
specifically-flagged strike -- the dodging combatant's own simultaneous
strike against the attacker is unaffected either way. `[pot]`'s strike
carries no such flag: it is an ordinary, fully dodgeable hand strike
substitute.

"[cel] Strike: dodge, with 1 additional strike (limited).": one single
strike choice that bundles two effects inseparably (confirmed by the
`[ANK 20220204]` ruling below) -- the `[cel]` clause is never "just a dodge"
or "just an additional strike," always both together when chosen. Modeled as
two paired hook registrations:
  - a `"combat_dodge_option"` provider (`engine/combat.py::
    COMBAT_DODGE_OPTION_HOOK`): choosing it resolves this strike as a dodge
    (0 damage, engine-enforced; protects from the opponent's simultaneous
    strike, engine-enforced) *and* its own `apply()` records that this
    vampire now has one additional-strike grant available.
  - a `"combat_additional_strike"` provider (`engine/combat.py::
    COMBAT_ADDITIONAL_STRIKE_HOOK`): offers "use the granted additional
    strike" only while that recorded grant is still available; using it
    consumes the grant (the resulting additional strike itself then goes
    through the engine's own full, independent strike-choice machinery --
    `engine/combat.py::_ask_additional_strike`'s own contract -- never a
    fixed/hardcoded hand strike).

"(limited)" / "The additional strike is not optional: you cannot play it for
the dodge only if you already played it for a (limited) additional strike
this round" [ANK 20220204]: per `engine/combat.py`'s own module docstring
("The '(limited)'/'one card or effect per round' cap itself is the
*granting* card's own business ... not this generic mechanism's"), this
card's own module tracks it, the same "card module owns its own '(limited)'
bookkeeping" convention `_shared.py::bleed_bookkeeping` already established
for Threats/Bonding -- but that specific helper is keyed off `pending`, the
per-*minion-action* scratch container `engine/action.py::
perform_minion_action` threads through *bleed* actions (OQ-11); `engine/
combat.py`'s three combat hooks (`"combat_strike_option"`/
`"combat_dodge_option"`/`"combat_additional_strike"`) carry no equivalent
object in their context (confirmed by re-reading `_ask_strike`/
`_resolve_strike_pair`/`_ask_additional_strike`/`run_combat` in full: no
round counter, no scratch dict, nothing distinguishing "this is the normal
strike pair" from "this is an additional-strike pair" is threaded anywhere
a hook provider can see), so `bleed_bookkeeping` itself does not apply here
and a different, self-contained mechanism is used instead (`_cel_book`,
below).

Deliberate, documented granularity simplification (not a guess): with no
round-boundary (or even combat-boundary) signal exposed by `engine/
combat.py` to a hook provider, this module cannot distinguish "a new round
has started" from "this is still the same round" purely from the context a
provider receives (`player`/`vampire`/`opponent`, identical shape on every
call). Enforcing the ruling exactly ("per round of combat") would need a
small, round-scoped scratch container threaded through `run_combat`'s three
hook contexts, mirroring `pending`'s role for minion actions (OQ-11) --
genuinely new `engine/combat.py` scope, out of bounds for a card module
(CLAUDE.md "No engine patches ... hand off to rules-engineer"). Instead,
`_cel_book` tracks the "(limited)" grant per *vampire instance*, for as long
as that instance exists (i.e. "once per game" rather than precisely "once
per round"): once this vampire has played `[cel]` once, the clause is never
offered to it again, for the rest of the game, regardless of how many
further rounds or separate combats follow. This is strictly *more*
restrictive than the sourced ruling, never less -- it can never produce the
rules-forbidden outcome (re-granting an additional strike in the same round,
or replaying `[cel]` "for the dodge only" after the grant was already used
this round), only the safe-direction cost of also disallowing a later,
separate, legitimate replay (a different physical copy, a later round or a
later combat) that the rules would in fact allow. Flagged here, and in the
hand-off report, as a candidate for a future `rules-engineer` pass (a
round-scoped scratch container for `engine/combat.py`, parallel to `pending`)
if exact per-round fidelity is ever needed; no test below exercises (or
claims) correct round-2 re-availability, only the same-round restriction the
ruling actually describes.
"""

import weakref
from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.cards import Sect
from vtesbot.engine.combat import (
    COMBAT_ADDITIONAL_STRIKE_HOOK,
    COMBAT_DODGE_OPTION_HOOK,
    COMBAT_STRENGTH_MODIFIER_HOOK,
    COMBAT_STRIKE_OPTION_HOOK,
    HAND_STRIKE_STRENGTH,
    StrikeDamage,
)
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 100597
ANI = "ani"
CEL = "cel"
POT = "pot"

CEL_PLAYED_KEY = "played"
CEL_GRANT_AVAILABLE_KEY = "grant_available"

# Per-vampire "(limited)" bookkeeping for the `[cel]` clause -- see module
# docstring for why this cannot use the shared `_shared.bleed_bookkeeping`/
# `pending` convention (no equivalent scratch object exists in
# `engine/combat.py`'s hook contexts), and why the chosen granularity is
# "once per vampire instance" rather than "once per round".
#
# `VampireInPlay` (`engine/state.py`) is a plain `@dataclass` with no
# `frozen=True`/`unsafe_hash=True`, so (per Python's own dataclass rules:
# `eq=True` + `frozen=False` => `__hash__ = None`) it is unhashable and
# cannot be used as a `dict`/`WeakKeyDictionary` key directly (a
# `WeakKeyDictionary` still hashes the wrapped key internally, so it hits
# the identical problem). Keyed instead by `id(vampire)` in a plain
# module-level `dict`, paired with a `weakref.finalize` callback that pops
# the entry the instant this specific vampire object is garbage-collected
# -- this is what actually prevents the "`id()` gets reused after
# garbage-collection" footgun from leaking a stale flag into an unrelated,
# later vampire object that happens to receive the same `id()` (e.g. a
# different test's own "P1-V1"): by the time any id could be reused, the
# original object's entry is already gone.
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
    """The vampire whose own strike/dodge/additional-strike choice this hook
    offer is for -- `context["player"]` is always that vampire's own
    controller (see `engine/combat.py::_ask_strike`/`_ask_additional_strike`
    call sites: `hooks.offer(HOOK, state, player=player, vampire=vampire.
    instance_id, opponent=opponent.instance_id)`)."""
    return state.players[context["player"]].vampires.get(context["vampire"])


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _requires_an_anarch(vampire: VampireInPlay | None) -> bool:
    return vampire is not None and vampire.card.sect is Sect.ANARCH


def _base_hand_strike_damage(state: GameState, context: Mapping[str, Any]) -> int:
    """The damage a plain hand strike would deal right now (`engine/
    combat.py::_strike_strength`'s own computation): base strength plus any
    live `"combat_strength_modifier"` contribution -- so this card's own
    "+1"/"+2 damage" stacks with, rather than replaces, any other strength
    bonus already in play, per "[ani] [pot] Additional damage inherits all
    of the properties of the base damage" [TOM 19960225]."""
    return HAND_STRIKE_STRENGTH + hooks.sum_modifiers(
        COMBAT_STRENGTH_MODIFIER_HOOK,
        state,
        player=context["player"],
        vampire=context["vampire"],
        opponent=context["opponent"],
    )


def _provide_ani(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[ani] Strike: hand strike at +1 damage. This strike cannot be
    dodged." -- see module docstring for the dodge-proof `StrikeDamage` flag
    and the base-damage computation."""
    vampire = _controllers_vampire(state, context)
    if not _requires_an_anarch(vampire):
        return []
    disciplines = vampire.card.disciplines  # type: ignore[union-attr]
    if ANI not in disciplines and ANI.upper() not in disciplines:
        return []
    player = context["player"]
    if not _has_card_in_hand(state, player):
        return []
    base = _base_hand_strike_damage(state, context)

    def _apply(s: GameState) -> StrikeDamage:
        play_from_hand(s, player, KRCG_ID)
        return StrikeDamage(amount=base + 1, ignore_dodge=True)

    return [
        HookOption(
            choice=Choice("dust_up:ani", "Dust Up [ani]: hand strike +1, cannot be dodged"),
            apply=_apply,
        )
    ]


def _provide_pot(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[pot] Strike: hand strike at +2 damage." -- an ordinary, dodgeable
    hand-strike substitute (no `ignore_dodge`); see module docstring for the
    base-damage computation."""
    vampire = _controllers_vampire(state, context)
    if not _requires_an_anarch(vampire):
        return []
    disciplines = vampire.card.disciplines  # type: ignore[union-attr]
    if POT not in disciplines and POT.upper() not in disciplines:
        return []
    player = context["player"]
    if not _has_card_in_hand(state, player):
        return []
    base = _base_hand_strike_damage(state, context)

    def _apply(s: GameState) -> StrikeDamage:
        play_from_hand(s, player, KRCG_ID)
        return StrikeDamage(amount=base + 2, ignore_dodge=False)

    return [
        HookOption(
            choice=Choice("dust_up:pot", "Dust Up [pot]: hand strike +2 damage"),
            apply=_apply,
        )
    ]


def _provide_cel_dodge(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[cel] Strike: dodge, with 1 additional strike (limited)." -- see
    module docstring for why this is split across this hook (the dodge
    itself, plus recording the grant) and `_provide_cel_additional_strike`
    (claiming the grant), and for the "(limited)" granularity this module
    enforces."""
    vampire = _controllers_vampire(state, context)
    if not _requires_an_anarch(vampire):
        return []
    disciplines = vampire.card.disciplines  # type: ignore[union-attr]
    if CEL not in disciplines and CEL.upper() not in disciplines:
        return []
    player = context["player"]
    if not _has_card_in_hand(state, player):
        return []
    book = _cel_book(vampire)  # type: ignore[arg-type]
    if book.get(CEL_PLAYED_KEY):
        return []  # "(limited)": already played this card's [cel] clause.

    def _apply(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        book[CEL_PLAYED_KEY] = True
        book[CEL_GRANT_AVAILABLE_KEY] = True

    return [
        HookOption(
            choice=Choice(
                "dust_up:cel", "Dust Up [cel]: dodge, with 1 additional strike (limited)"
            ),
            apply=_apply,
        )
    ]


def _provide_cel_additional_strike(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """Claims the additional-strike grant `_provide_cel_dodge` recorded.
    Not itself re-gated on "Requires an Anarch"/discipline/hand: those were
    already checked at grant time, and consuming an already-legitimately-
    granted strike needs no re-check (nothing in the rules revokes a granted
    additional strike mid-round)."""
    vampire = _controllers_vampire(state, context)
    if vampire is None:
        return []
    book = _cel_book(vampire)
    if not book.get(CEL_GRANT_AVAILABLE_KEY):
        return []

    def _apply(s: GameState) -> None:
        book[CEL_GRANT_AVAILABLE_KEY] = False

    return [
        HookOption(
            choice=Choice(
                "dust_up:cel_additional_strike", "Dust Up [cel]: use the granted additional strike"
            ),
            apply=_apply,
        )
    ]


hooks.register(COMBAT_STRIKE_OPTION_HOOK, _provide_ani)
hooks.register(COMBAT_STRIKE_OPTION_HOOK, _provide_pot)
hooks.register(COMBAT_DODGE_OPTION_HOOK, _provide_cel_dodge)
hooks.register(COMBAT_ADDITIONAL_STRIKE_HOOK, _provide_cel_additional_strike)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Dust Up",
        status=Status.IMPLEMENTED,
        hooks=(
            Hook.COMBAT_STRIKE_OPTION,
            Hook.COMBAT_DODGE_OPTION,
            Hook.COMBAT_ADDITIONAL_STRIKE,
        ),
        source=__name__,
    )
)
