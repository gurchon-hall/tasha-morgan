"""Organized Resistance (Reaction). krcg id 102230.

Card text (verbatim, via `krcg.load()` + `msgspec.json.encode()` in the
project's `uv run` virtualenv (krcg 5.14), 2026-10-15, matching the raw
snapshot saved to `data/cards/102230.json`; independently re-verified by
`rules-auditor` against the live `api.krcg.org/card/102230` response, which
agrees byte-for-byte. Note: the `krcg.vtes.VTES`/`.card_text` API this
module originally cited only exists in plain `python`'s pip-installed
krcg 4.18, not in this venv's newer 5.14 -- that snapshot was replaced
2026-10-15 after it was found to have drifted from the current `api.krcg.org`
data on several fields, `legal` among them):
    "Requires a baron. Usable by a locked baron.
    An Anarch you control gets +1 intercept. Also usable to unlock a locked
    Anarch you control; that Anarch attempts to block with +1 intercept,
    even if intercept is not yet needed."

Rulings (verbatim, via krcg; `cards["Organized Resistance"].rulings`):
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
(free). Legal since 2021-12-31; confirmed on the active 2P allowed list
(`data/formats/2p/2026-10-03.json`).

Status: implemented (OQ-26, `docs/OPEN_QUESTIONS.md`, resolved -- the
engine gap this card was blocked on, `Hook.BLOCK_CANDIDATE_INJECTION` /
`engine/action.py::BLOCK_CANDIDATE_INJECTION_HOOK`, was built and
independently audited by `rules-auditor` with no blocking findings; this
module wires the card's own two clauses against it and against the
pre-existing `INTERCEPT_MODIFIER_HOOK`).

"Requires a baron. Usable by a locked baron.": per Rulebook §6 Vampire
Sects/Titles (same convention `protection_racket.py`'s docstring documents
for "Requires an Anarch"), this gates *which vampire plays the card* -- a
vampire the player controls with printed title "Baron". Normally a
Reaction card also requires its playing minion to be ready and unlocked
(§8 glossary), but this card's second sentence relaxes that to just
`zone == "ready"` (in play, not torpor) -- a locked baron may still play
it. Both clauses share one `_eligible_barons` helper for this gate.

"An Anarch you control gets +1 intercept.": the recipient ("an Anarch you
control") need not be the playing Baron. Structural gate, not a ruling:
`engine/action.py::attempt_block` fixes *which* vampire is attempting to
block before `_duel_stealth_intercept` (the sole `INTERCEPT_MODIFIER_HOOK`
call site) ever runs, so there is exactly one live intercept total in
flight, scoped to that one already-fixed candidate -- a named-recipient
clause can only have an observable effect when that recipient *is* the
fixed candidate. `_duel_stealth_intercept` already threads that candidate
into the hook's context as `context["blocking_vampire"]`, so the gate is
simply "is `context['blocking_vampire']` one of `player`'s own Anarch
vampires," read fresh on every `offer()` call. (Rulebook §4 "Stealth and
Intercept" describes intercept as the blocking minion's own property,
corroborating this reading, per a `rules-auditor` review; not itself the
load-bearing citation.) Missing `blocking_vampire` context (hook asked
outside the real block-attempt flow) degrades to "no bonus." One
`HookOption` per eligible Baron; the bonus is a flat `+1` with nothing
further to compute once the gate is satisfied.

"Also usable to unlock a locked Anarch you control; that Anarch attempts
to block with +1 intercept, even if intercept is not yet needed.": wired
against `Hook.BLOCK_CANDIDATE_INJECTION`. Candidate vampire: `player`'s own
`zone == "ready"`, `locked is True`, `card.sect is Sect.ANARCH`. One option
per (eligible Baron, eligible locked Anarch) pair -- unlike clause 1, which
Anarch is chosen here has an observable effect (it is the one unlocked and
forced to block), and which Baron played the card matters for the
"once per minion across both clauses" bookkeeping below if the player
controls more than one Baron. `apply(state)` plays the card, unlocks the
chosen Anarch, and returns that `VampireInPlay`, per
`BLOCK_CANDIDATE_INJECTION_HOOK`'s own contract -- `attempt_block` then
returns it as an immediate, unconditional successful block, matching the
ruling "the block attempt still happens, as does the resulting combat if
the block is successful" [LSJ 20090514].

"Can be used by a vampire who is already attempting to block." [ANK
20181122-2]: needs no special-case code -- `attempt_block` does not lock a
block candidate until *after* that candidate's attempt succeeds, so a
same-action Baron mid-way through an ordinary block attempt is still
`zone == "ready"`/unlocked and offered either clause, and
`BLOCK_CANDIDATE_INJECTION_HOOK` is re-offered on every retry, including
after an earlier attempt by a different vampire already failed this
action. Proven by `tests/cards/test_organized_resistance.py::
test_can_be_used_after_an_earlier_ordinary_block_attempt_already_failed_this_action`.

"Cannot be used if the vampire cannot attempt to block the action (eg.
{Daring the Dawn})." [LSJ 20010714-2]: automatically satisfied --
`attempt_block` is simply not invoked for an action that cannot be
blocked, so neither hook is offered. Daring the Dawn itself is not
implemented in this project, so the scenario this ruling guards against is
not constructible with the current card pool (not reachable today, but
correctly modeled either way, per `dust_up.py`'s OQ-21 citation).

"Counts as requiring an Anarch (for eg. {Powerbase: Los Angeles})." [LSJ
20080603] [LSJ 20050128]: a rule for *other* cards checking "was this
played by an Anarch-requiring card"; Powerbase: Los Angeles is not
implemented, so nothing today consumes such a flag.

"Does not ignore the normal prey, predator or target restrictions." [ANK
20180623]: automatically satisfied -- `attempt_block`'s own `defender`
parameter scopes every candidate, hardcoded or injected, to the single 2P
opponent, structurally both prey and predator (CLAUDE.md §3); both
providers below are likewise only ever offered `player=defender`.

§8 glossary: "A minion cannot play the same reaction card more than once
during a single action (even if using a different Discipline level)."
Read as keying the restriction on the *physical card use by one minion*,
not on which of the card's alternative effects that minion chose -- this
card's two clauses are two such alternative effects. Both providers share
one `USED_BY_KEY` scratch set, keyed on the *Baron's* own instance id, in
the shared per-action `pending` dict (OQ-11): a Baron that already played
clause 1 this action is excluded from `_eligible_barons` for clause 2, and
vice versa; a *different* eligible Baron is unaffected (mirrors
`protection_racket.py`'s "restricts the same minion, not the whole
Methuselah" precedent).
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
CARD_TYPE = "Reaction"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): matches
this module's own "Card type: Reaction" docstring fact above."""


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
    see module docstring's Rulebook §4 "Stealth and Intercept" citation:
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
            played_card_type=CARD_TYPE,
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
            played_card_type=CARD_TYPE,
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
