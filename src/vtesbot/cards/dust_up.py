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
this round" [ANK 20220204]: tracked via `engine/combat.py`'s shared,
round-scoped `additional_strike_limit_used`/`mark_additional_strike_limit_
used` helpers (`docs/OPEN_QUESTIONS.md` OQ-19) -- `run_combat` threads one
fresh scratch dict per round into both `"combat_dodge_option"`'s and
`"combat_additional_strike"`'s own hook context, so this flag is correctly
shared *across* different cards/physical copies (closing the gap this
module's own private, per-vampire-*instance*, effectively-forever tracking
previously left open: nothing stopped a vampire holding both Dust Up and a
second "(limited)" additional-strike card, e.g. Side Strike, from using both
grants in the same round) and correctly resets every round (unlike the
previous tracking, which never reset at all for the life of the vampire
object). The `[cel]` dodge provider below gates its own offer on `not
additional_strike_limit_used(context)` and its `apply()` calls `mark_
additional_strike_limit_used(context)` -- per the ANK ruling, the check
belongs at the *granting* clause (the dodge-bundled grant here), not at the
later act of claiming an already-recorded grant via `_provide_cel_
additional_strike`, which needs no re-check of its own.
"""

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
    additional_strike_limit_used,
    mark_additional_strike_limit_used,
)
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 100597
ANI = "ani"
CEL = "cel"
POT = "pot"

CEL_GRANTS_KEY = "dust_up_cel_grants"
"""Context key for the one piece of state still genuinely private to this
card's own `[cel]` clause: *which vampires* currently have a still-unclaimed
dodge-bundled grant from this card, distinct from the cross-card "(limited)"
cap (`additional_strike_limit_used`, above) -- a vampire's grant can be
consumed (claimed via `_provide_cel_additional_strike`) independently of
whether the shared cross-card cap has since been set by a *different*
vampire's own (unrelated) "(limited)" play. Stored as a `dict[str, bool]`
(vampire instance id -> grant available) *nested inside* the shared
`round_state` dict `engine/combat.py` threads into this hook's context,
under this module's own key (so it cannot collide with `engine/combat.py`'s
own `ADDITIONAL_STRIKE_LIMIT_KEY`) -- `round_state` itself is one single
object shared by *both* combatants' hook calls this round (`engine/
combat.py::run_combat` passes the identical dict regardless of which
combatant is being asked), so a flat, un-keyed boolean here would wrongly
conflate one vampire's grant with the other's; keying by vampire instance
id avoids that while still getting this per-card flag's round-scoped
lifetime for free from `round_state`'s own round-scoped lifetime -- no
separate per-vampire-instance-forever bookkeeping needed any more."""


def _round_state(context: Mapping[str, Any]) -> dict[str, Any] | None:
    """The shared `round_state` dict `engine/combat.py` threads into
    `"combat_dodge_option"`/`"combat_additional_strike"` contexts, or `None`
    if this hook was offered directly, bypassing `run_combat` (some scenario
    tests do this to probe one hook in isolation) -- mirrors `engine/
    combat.py::additional_strike_limit_used`'s own "missing key => no shared
    state available" degrade-gracefully reasoning for this card's own
    `CEL_GRANTS_KEY` bucket."""
    return context.get("round_state")


def _cel_grant_available(round_state: dict[str, Any] | None, vampire_id: str) -> bool:
    """Whether `vampire_id` currently has an unclaimed `[cel]` grant from
    this card. A missing `round_state` (see `_round_state`) is treated as
    "no grant available" -- there is nothing to persist across separate
    calls in that case, matching `additional_strike_limit_used`'s own
    degrade-gracefully convention."""
    if round_state is None:
        return False
    return bool(round_state.get(CEL_GRANTS_KEY, {}).get(vampire_id))


def _set_cel_grant_available(
    round_state: dict[str, Any] | None, vampire_id: str, value: bool
) -> None:
    """Record `vampire_id`'s `[cel]` grant as available/consumed. A missing
    `round_state` is a no-op (nothing to persist to)."""
    if round_state is not None:
        round_state.setdefault(CEL_GRANTS_KEY, {})[vampire_id] = value


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
    (claiming the grant), and for the cross-card "(limited)" cap this
    provider now consults/records via `engine/combat.py`'s shared, round-
    scoped helpers."""
    vampire = _controllers_vampire(state, context)
    if not _requires_an_anarch(vampire):
        return []
    disciplines = vampire.card.disciplines  # type: ignore[union-attr]
    if CEL not in disciplines and CEL.upper() not in disciplines:
        return []
    player = context["player"]
    if not _has_card_in_hand(state, player):
        return []
    if additional_strike_limit_used(context):
        return []  # "(limited)": a grant (this card's or another's) was already used this round.
    round_state = _round_state(context)
    vampire_id = context["vampire"]

    def _apply(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        mark_additional_strike_limit_used(context)
        _set_cel_grant_available(round_state, vampire_id, True)

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
    Not itself re-gated on "Requires an Anarch"/discipline/hand/the shared
    "(limited)" cap: those were already checked at grant time, and consuming
    an already-legitimately-granted strike needs no re-check (nothing in
    the rules revokes a granted additional strike mid-round) -- per Dust
    Up's own ruling ("you cannot play it for the dodge only if you already
    played it for a (limited) additional strike this round" [ANK 20220204]),
    the cap gates the *granting* clause only."""
    vampire = _controllers_vampire(state, context)
    if vampire is None:
        return []
    round_state = _round_state(context)
    vampire_id = context["vampire"]
    if not _cel_grant_available(round_state, vampire_id):
        return []

    def _apply(s: GameState) -> None:
        _set_cel_grant_available(round_state, vampire_id, False)

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
