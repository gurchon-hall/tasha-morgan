"""Organized Resistance (Reaction). krcg id 102230.

Card text (verbatim, via the installed `krcg` 5.14 package's own
`krcg.vtes.VTES["Organized Resistance"].card_text`, 2026-10-12, matching the
raw snapshot saved to `data/cards/102230.json`; independently re-verified by
`rules-auditor` against the live `api.krcg.org/card/102230` response, which
agrees byte-for-byte -- note for a future reproduction attempt: a plain
`python -c "from krcg.vtes import VTES; VTES.load()"` resolves this import
in this project's own environment, but the separate `uv run` virtualenv
installs an older `krcg` without the `vtes` submodule at all, same
pre-existing gap `tests/cards/test_octane.py`/`test_siarhei_levchenko.py`
already hit under `uv run pytest`):
    "Requires a baron. Usable by a locked baron.
    An Anarch you control gets +1 intercept. Also usable to unlock a locked
    Anarch you control; that Anarch attempts to block with +1 intercept,
    even if intercept is not yet needed."

Rulings (verbatim, via krcg; `VTES["Organized Resistance"].rulings`):
    - "Counts as requiring an Anarch (for eg. {Powerbase: Los Angeles})."
      [LSJ 20080603] [LSJ 20050128]
    - "If the action lacks a suitable target because of the unlock (e.g.
      {Ambush}), the block attempt still happens, as does the resulting
      combat if the block is successful." [LSJ 20090514]
    - "Can be used by a vampire who is already attempting to block."
      [ANK 20181122-2]
    - "Cannot be used if the vampire cannot attempt to block the action (eg.
      {Daring the Dawn})." [LSJ 20010714-2]
    - "Does not ignore the normal prey, predator or target restrictions."
      [ANK 20180623]

Card type: Reaction (`types == ["Reaction"]`). `discipline_requirement is
None`, `clans is None` -- no Discipline or clan requirement at all
(confirmed by the installed package's own `disciplines == []`, `clans is
None`); the only playability gate is the printed "Requires a baron"
sentence plus the "Usable by a locked baron" relaxation. `cost is None`
(free). Legal since 2021-12-01; confirmed on the active 2P allowed list
(`data/formats/2p/2026-10-03.json`).

Status: implemented (OQ-26, `docs/OPEN_QUESTIONS.md`, resolved -- the
engine gap this card was blocked on, `Hook.BLOCK_CANDIDATE_INJECTION` /
`engine/action.py::BLOCK_CANDIDATE_INJECTION_HOOK`, was built and
independently audited by `rules-auditor` with no blocking findings; this
module wires the card's own two clauses against it and against the
pre-existing `INTERCEPT_MODIFIER_HOOK`).

"Requires a baron. Usable by a locked baron.": per Rulebook SS6 Vampire
Sects/Titles (same convention `protection_racket.py`'s own docstring
documents for "Requires an Anarch"), this gates *which vampire plays the
card* -- a vampire the player controls with printed title "Baron"
(`CryptCard.title == "Baron"`), normally also required to be `is_ready_
unlocked` for any Reaction card (SS8 glossary: "A card played by a
Methuselah's ready, unlocked minion..."), except that this card's own
second sentence explicitly relaxes that down to just `zone == "ready"`
(in play, not torpor) -- a locked (tapped) baron may still play it. Both
clauses below share one `_eligible_barons` helper for this gate, rather
than three separately-maintained copies of the same check (clause 1's
provider, clause 2's provider, and the "once per Baron across both
clauses" bookkeeping all read it the same way).

"An Anarch you control gets +1 intercept.": the first effect clause --
textually distinct from the playing vampire (the Baron): the recipient is
"an Anarch you control", not necessarily the Baron itself. The decisive
argument for this clause's gate is structural, not a ruling: `engine/
action.py::attempt_block` already fixes *which* vampire is attempting to
block (via the `"block_attempt"` `Decision`) *before* `_duel_stealth_
intercept` ever runs, and that function is the sole call site for
`INTERCEPT_MODIFIER_HOOK` -- there is exactly one live intercept total in
flight per call, scoped to that one already-fixed candidate. A clause that
names a specific recipient ("an Anarch you control") can therefore only
have an observable effect when that named recipient *is* the already-fixed
candidate; there is no code path in this already-built, already-audited
engine by which naming some other, uninvolved Anarch could matter. (Per a
`rules-auditor` review of this clause specifically: Rulebook SS4 "Stealth
and Intercept" -- "Intercept represents the blocking minion's efforts...",
and its worked example, "[h]er predator ... plays a reaction card to give
+1 intercept to one of her ready unlocked minions, Ayelech ... Ayelech is
locked, and combat begins" -- is *consistent* with this reading, intercept
being described there as the blocking minion's own property, but that one
example does not by itself settle the general question for every
named-recipient card; it is corroborating context, not the load-bearing
citation here.) `engine/action.py::_duel_stealth_intercept`
already threads exactly the needed information into the hook's own context
as `context["blocking_vampire"]`, so no new engine mechanism is needed: the
gate is simply "is `context['blocking_vampire']` one of `player`'s own
Anarch vampires," read fresh on every single `offer()` call (same "live,
not cached" discipline `protection_racket.py`'s own titled-check uses for
its own context-sourced check). `context.get("blocking_vampire") is None`
(the hook is asked outside the real block-attempt flow, e.g. a direct
unit test) degrades to "no bonus," never a guess. Gated also on at least
one eligible Baron (see above) to actually play the card. One
`HookOption` per eligible Baron (mirroring `protection_racket.py`'s own
"one option per eligible [playing] vampire" shape); the bonus itself is a
flat `+1`, added the same way `protection_racket.py`'s own unqualified
"+1 intercept" clause is -- the engine's `_duel_stealth_intercept` ping-
pong already scopes every `INTERCEPT_MODIFIER_HOOK` offer to the one
block attempt currently in progress, so, once the named-recipient gate
above is satisfied, there is nothing further to compute.

"Also usable to unlock a locked Anarch you control; that Anarch attempts
to block with +1 intercept, even if intercept is not yet needed.": the
second effect clause, now wired against `Hook.BLOCK_CANDIDATE_INJECTION`
(`engine/action.py::BLOCK_CANDIDATE_INJECTION_HOOK`). Candidate vampire:
`player`'s own `zone == "ready"`, `locked is True`, `card.sect is
Sect.ANARCH`. One option per (eligible Baron, eligible locked Anarch)
pair -- unlike clause 1, here *which* Anarch is chosen has an observable
effect (it is the one unlocked and forced to block), so the Anarch
dimension cannot be collapsed away the way clause 1's can; the Baron
dimension still matters too, because which Baron is recorded as "having
played this card" this action is exactly what the "once per minion
across both clauses" bookkeeping below needs to track correctly in the
(rare, but not ruled out) case of a player controlling more than one
Baron. `apply(state)` plays the card, unlocks the chosen Anarch, and
returns that same `VampireInPlay` instance, per `BLOCK_CANDIDATE_
INJECTION_HOOK`'s own contract -- `attempt_block` then returns it
directly as an immediate, unconditional successful block, never
consulting `_duel_stealth_intercept`'s "only when needed" ping-pong for
it, matching the first ruling on file: "the block attempt still happens,
as does the resulting combat if the block is successful" [LSJ 20090514].

"Can be used by a vampire who is already attempting to block." [ANK
20181122-2]: needs no special-case code. Neither provider below ever
excludes a Baron merely because it is also the vampire currently
mid-way through an ordinary block attempt's stealth/intercept ping-pong
(`engine/action.py::attempt_block` does not lock a chosen block candidate
until *after* that candidate's attempt succeeds, so a same-action Baron
serving as the current, not-yet-resolved ordinary blocker is still
`zone == "ready"`/unlocked and still offered either clause by
`_eligible_barons`); and `BLOCK_CANDIDATE_INJECTION_HOOK` is re-offered
by `attempt_block` every time around its own retry loop, including after
an earlier ordinary attempt by a different vampire has already failed
this same action -- i.e. this clause is not restricted to being the
*first* block attempt of the window. Proven by
`tests/cards/test_organized_resistance.py::
test_can_be_used_after_an_earlier_ordinary_block_attempt_already_failed_this_action`,
the only shape of "already attempting to block" this engine's
sequential, one-attempt-at-a-time decision model can construct (there is
no engine notion of two *concurrent* block attempts in progress at once
to additionally test).

"Cannot be used if the vampire cannot attempt to block the action (eg.
{Daring the Dawn})." [LSJ 20010714-2]: automatically satisfied by this
card's own call sites -- `engine/action.py::attempt_block` is simply not
invoked at all for an action that cannot be blocked in the first place,
so neither hook is ever offered. Daring the Dawn itself is not
implemented in this project (not in `data/decks/vekn-2p/*.json`'s
suggested decklists seen so far), so the specific "a normally-blockable
action is made unblockable by some other effect" scenario this ruling
guards against is not constructible with the current card pool -- same
"not reachable today, but correctly modeled either way" status
`dust_up.py`'s own OQ-21 citation uses for an analogous not-yet-reachable
branch.

"Counts as requiring an Anarch (for eg. {Powerbase: Los Angeles})." [LSJ
20080603] [LSJ 20050128]: a rule for *other* cards that check "was this
played by an Anarch-requiring card" (Powerbase: Los Angeles is not
implemented in this project); nothing in this module needs to act on it,
since nothing today consumes such a flag.

"Does not ignore the normal prey, predator or target restrictions." [ANK
20180623]: automatically satisfied -- `attempt_block`'s own `defender`
parameter already scopes every candidate offered to either hook, hardcoded
or injected, to the single 2P opponent, which is structurally both prey
and predator (CLAUDE.md SS3); `_provide_organized_resistance_intercept`
and `_provide_organized_resistance_block_candidate` below are likewise
only ever offered `player=defender` by their respective hooks' sole call
sites, so neither can be used to affect anyone but the single eligible
opponent.

SS8 glossary, same page as the Reaction Card definition: "A minion cannot
play the same reaction card more than once during a single action (even
if using a different Discipline level)." Decision taken for this card's
two textually distinct usable effects (the task this module resolves
explicitly calls for this choice to be made deliberately, not guessed):
read "even if using a different Discipline level" as establishing the
general principle that the restriction is keyed on the *physical card use
by one minion*, not on which of the card's printed alternative effects
that minion chose -- a Discipline-leveled Reaction card's basic and
superior modes are two textually distinct effects on the same card
exactly the way this card's two clauses are, and SS8 is explicit that
choosing the *other* one does not grant a second use. Both providers
below therefore share one `USED_BY_KEY` scratch set, keyed on the
*Baron's* own instance id, in the shared per-action `pending` dict (OQ-11)
-- a Baron that already played clause 1 this action is excluded from
`_eligible_barons` for clause 2 this same action, and vice versa. Two
*different* eligible Barons (if the player controls more than one) are
each unaffected by the other's use, mirroring `protection_racket.py`'s own
"restricts the same minion, not the whole Methuselah" precedent.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import BLOCK_CANDIDATE_INJECTION_HOOK, INTERCEPT_MODIFIER_HOOK
from vtesbot.engine.cards import Sect
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 102230
USED_BY_KEY = "organized_resistance_used_by"


def _eligible_barons(state: GameState, player: str, used_by: set[str]) -> list[VampireInPlay]:
    """Candidate *playing* vampires for either clause: `player`'s own
    in-play ("ready", locked-or-not -- the card's own "Usable by a locked
    baron" relaxation, see module docstring) Barons that have not already
    played this card (either clause) this action."""
    return [
        v
        for v in state.players[player].vampires.values()
        if v.zone == "ready" and v.instance_id not in used_by and v.card.title == "Baron"
    ]


def _blocking_vampire_is_controlled_anarch(
    state: GameState, player: str, context: Mapping[str, Any]
) -> bool:
    """Whether the vampire currently attempting to block
    (`context["blocking_vampire"]`, threaded in by `engine/action.py::
    _duel_stealth_intercept`) is one of `player`'s own Anarch vampires --
    see module docstring's Rulebook SS4 "Stealth and Intercept" citation:
    intercept is always a property of the blocking minion, so a card
    naming a specific recipient only has an effect when that recipient is
    the vampire currently attempting the block. Missing context (the hook
    asked outside the real block-attempt flow) degrades to "no," never a
    guess."""
    blocking_vampire_id = context.get("blocking_vampire")
    if blocking_vampire_id is None:
        return False
    blocker = state.players[player].vampires.get(blocking_vampire_id)
    return blocker is not None and blocker.card.sect is Sect.ANARCH


def _eligible_locked_anarchs(state: GameState, player: str) -> list[VampireInPlay]:
    """Candidate vampires for clause 2's unlock: `player`'s own in-play,
    currently-*locked* Anarch vampires ("a locked Anarch you control")."""
    return [
        v
        for v in state.players[player].vampires.values()
        if v.zone == "ready" and v.locked and v.card.sect is Sect.ANARCH
    ]


def _used_by(pending: dict[str, Any] | None) -> set[str]:
    if pending is None:
        return set()
    return pending.setdefault(USED_BY_KEY, set())


def _provide_organized_resistance_intercept(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    player = context["player"]  # INTERCEPT_MODIFIER_HOOK is only ever offered to the defender.
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []
    if not _blocking_vampire_is_controlled_anarch(state, player, context):
        return []

    used_by = _used_by(context.get("pending"))
    barons = _eligible_barons(state, player, used_by)
    if not barons:
        return []

    def _make_apply(baron: VampireInPlay) -> Any:
        def _apply(s: GameState) -> int:
            play_from_hand(s, player, KRCG_ID)
            used_by.add(baron.instance_id)
            return 1

        return _apply

    return [
        HookOption(
            choice=Choice(
                f"organized_resistance:intercept:{baron.instance_id}",
                f"Organized Resistance: an Anarch you control gets +1 intercept"
                f" ({baron.card.name})",
            ),
            apply=_make_apply(baron),
        )
        for baron in barons
    ]


def _provide_organized_resistance_block_candidate(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    player = context["player"]  # offered only to defender, see BLOCK_CANDIDATE_INJECTION_HOOK.
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    used_by = _used_by(context.get("pending"))
    barons = _eligible_barons(state, player, used_by)
    if not barons:
        return []
    anarchs = _eligible_locked_anarchs(state, player)
    if not anarchs:
        return []

    def _make_apply(baron: VampireInPlay, anarch: VampireInPlay) -> Any:
        def _apply(s: GameState) -> VampireInPlay:
            play_from_hand(s, player, KRCG_ID)
            anarch.locked = False
            used_by.add(baron.instance_id)
            return anarch

        return _apply

    return [
        HookOption(
            choice=Choice(
                f"organized_resistance:unlock:{anarch.instance_id}:by:{baron.instance_id}",
                f"Organized Resistance: unlock and force-block with {anarch.card.name}"
                f" (played by {baron.card.name})",
            ),
            apply=_make_apply(baron, anarch),
        )
        for baron in barons
        for anarch in anarchs
    ]


hooks.register(INTERCEPT_MODIFIER_HOOK, _provide_organized_resistance_intercept)
hooks.register(BLOCK_CANDIDATE_INJECTION_HOOK, _provide_organized_resistance_block_candidate)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Organized Resistance",
        status=Status.IMPLEMENTED,
        hooks=(Hook.INTERCEPT_MODIFIER, Hook.BLOCK_CANDIDATE_INJECTION),
        source=__name__,
    )
)
