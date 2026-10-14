"""Second Tradition: Domain (Reaction). krcg id 101706.

Card text (verbatim, via the installed `krcg` 4.18 `krcg.vtes.VTES` package
-- the project's `uv run` virtualenv has a newer `krcg` (5.14) whose own
`krcg.load()` API has no `to_json()`/raw-schema equivalent, the same
pre-existing gap `organized_resistance.py`'s own docstring notes --
2026-10-14, matching the raw snapshot saved to `data/cards/101706.json`):
    "Requires a prince or justicar.
    [REACTION] +2 intercept.
    [REACTION] Only usable by a locked prince or justicar. This vampire
    burns 1 blood to unlock and attempt to block with +2 intercept, even
    if intercept is not yet needed."

Rulings (verbatim, via krcg; `VTES["Second Tradition: Domain"].rulings`):
    - "The burn blood effect is not reduced by effects that reduce the
      cost of the card (eg. {Adana de Sforza})." [ANK 20210226]
    - "The card cannot be played if the minion cannot afford to burn the
      blood." [ANK 20210226]
    - "If the action lacks a suitable target because of the unlock (e.g.
      {Ambush}), the block attempt still happens, as does the resulting
      combat if the block is successful." [LSJ 20090514]
    - "Can be used by a vampire who is already attempting to block."
      [ANK 20181122-2]
    - "Cannot be used if the vampire cannot attempt to block the action
      (eg. {Daring the Dawn})." [LSJ 20010714-2]
    - "Does not ignore the normal prey, predator or target restrictions."
      [ANK 20180623]

Card type: Reaction (`types == ["Reaction"]`). `clans == []`,
`disciplines == []` -- no clan/Discipline requirement at all; the only
playability gate is the printed "Requires a prince or justicar" sentence.
`blood_cost`/`pool_cost` are both `None` (clause 2's "burns 1 blood" is a
card-text in-play cost, not a printed play cost). Legal since 1994-09-15
(live `api.krcg.org` -- the installed krcg 4.18 package's bundled
snapshot this module's text/rulings were otherwise fetched from has this
one field stale); confirmed on the active 2P allowed list
(`data/formats/2p/2026-10-03.json`) and in `data/decks/vekn-2p/toreador.json`.

Status: implemented. Structurally identical to Organized Resistance
(krcg id 102230, `cards/organized_resistance.py`, OQ-26) -- "Requires a
baron"/"an Anarch you control gets +1 intercept"/"unlock a locked Anarch
... attempts to block with +1 intercept, even if intercept is not yet
needed" -- except both clauses here name the *same* vampire (the playing
prince/justicar is itself the one who may attempt to block, never a
separately-named recipient) and clause 2 has a real blood cost instead of
being free. Reuses `INTERCEPT_MODIFIER_HOOK`/`BLOCK_CANDIDATE_INJECTION_
HOOK` with no new engine work.

"Requires a prince or justicar": per Rulebook SS2 Card Types ("Requirements
for Playing Cards") and this project's own `protection_racket.py`
precedent ("Requires an Anarch" on a Reaction card gates the *reacting*
(playing) minion, not some other "acting minion"), checked as `card.title
in {"Prince", "Justicar"}` (the `engine/politics.py::TITLE_VOTES`/
`parity_shift.py::REQUIRED_TITLES` plain-capitalized-keyword convention).

Clause 1 ("[REACTION] +2 intercept."): unqualified, like Protection
Racket's own "+1 intercept" -- a flat bonus to whichever block attempt is
currently in progress, playable by any of `player`'s own ready, unlocked
qualifying vampires (no "is this vampire the one attempting to block"
check -- Rulebook SS4 "Stealth and Intercept" treats intercept as a
property of the *attempt*, not tied to the playing card's own identity
beyond eligibility to play it; `protection_racket.py`'s own module
docstring already establishes this reading for the project).

Clause 2 ("Only usable by a locked prince or justicar. This vampire burns
1 blood to unlock and attempt to block with +2 intercept, even if
intercept is not yet needed."): mirrors Organized Resistance's clause 2
exactly, with the "named recipient" and the "unlocking" vampire collapsed
into one and the same candidate (never two roles). Built against
`BLOCK_CANDIDATE_INJECTION_HOOK` (OQ-26): a chosen option pays the 1-blood
cost, unlocks the vampire, and is returned as an unconditional successful
blocker, per that hook's own contract and the cited rulings ("the block
attempt still happens ... if the block is successful"; "even if intercept
is not yet needed" already matches the hook's own offer point, which runs
every time around `attempt_block`'s retry loop, before any candidate is
otherwise needed). "The card cannot be played if the minion cannot afford
to burn the blood" [ANK 20210226]: gated on `vampire.blood >= BLOOD_COST`.
The cost-reduction ruling [ANK 20210226] has no reachable case (no
cost-reduction effect is implemented in this project yet).

"Can be used by a vampire who is already attempting to block."
[ANK 20181122-2] / "Cannot be used if the vampire cannot attempt to block
the action (eg. Daring the Dawn)." [LSJ 20010714-2] / "Does not ignore the
normal prey, predator or target restrictions." [ANK 20180623]: all three
need no special-case code, for exactly the reasons `organized_resistance.py`'s
own module docstring already gives (unlocked-until-success block
candidates are re-offered every retry; `attempt_block` is simply never
invoked for an unblockable action; every candidate, hardcoded or injected,
is already scoped to the single 2P opponent).

SS8 glossary "A minion cannot play the same reaction card more than once
during a single action": both clauses name the *same* vampire role, so one
shared `USED_BY_KEY` set (keyed by vampire instance id) suffices -- a
vampire that already played clause 1 this action cannot then play clause 2
(or a second copy of clause 1), and vice versa; a second, distinct eligible
prince/justicar is unaffected.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import BLOCK_CANDIDATE_INJECTION_HOOK, INTERCEPT_MODIFIER_HOOK
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101706
REQUIRED_TITLES = frozenset({"Prince", "Justicar"})
"""Verbatim "Requires a prince or justicar."."""
USED_BY_KEY = "second_tradition_domain_used_by"
BLOOD_COST = 1
"""Verbatim "burns 1 blood to unlock"."""
INTERCEPT_BONUS = 2
"""Verbatim "+2 intercept"."""
CARD_TYPE = "Reaction"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): matches
this module's own "Card type: Reaction" docstring fact above."""


def _is_titled_prince_or_justicar(vampire: VampireInPlay) -> bool:
    return vampire.card.title in REQUIRED_TITLES


def _used_by(pending: dict[str, Any] | None) -> set[str]:
    if pending is None:
        return set()
    return pending.setdefault(USED_BY_KEY, set())


def _eligible_unlocked(state: GameState, player: str, used_by: set[str]) -> list[VampireInPlay]:
    """Candidate vampires for clause 1: `player`'s own ready, unlocked
    princes/justicars that have not already played this card this action
    (standard Reaction-card eligibility, SS8 glossary)."""
    return [
        v
        for v in state.players[player].vampires.values()
        if v.is_ready_unlocked and v.instance_id not in used_by and _is_titled_prince_or_justicar(v)
    ]


def _eligible_locked(state: GameState, player: str, used_by: set[str]) -> list[VampireInPlay]:
    """Candidate vampires for clause 2: `player`'s own in-play, currently
    *locked* princes/justicars ("Only usable by a locked prince or
    justicar") that can afford the 1-blood cost and have not already
    played this card this action."""
    return [
        v
        for v in state.players[player].vampires.values()
        if v.zone == "ready"
        and v.locked
        and v.blood >= BLOOD_COST
        and v.instance_id not in used_by
        and _is_titled_prince_or_justicar(v)
    ]


def _provide_second_tradition_domain_intercept(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    player = context["player"]  # INTERCEPT_MODIFIER_HOOK is only ever offered to the defender.
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    used_by = _used_by(context.get("pending"))
    eligible = _eligible_unlocked(state, player, used_by)
    if not eligible:
        return []

    def _make_apply(vampire: VampireInPlay) -> Any:
        def _apply(s: GameState) -> int:
            play_from_hand(s, player, KRCG_ID)
            used_by.add(vampire.instance_id)
            return INTERCEPT_BONUS

        return _apply

    return [
        HookOption(
            choice=Choice(
                f"second_tradition_domain:intercept:{vampire.instance_id}",
                f"Second Tradition: Domain: +{INTERCEPT_BONUS} intercept ({vampire.card.name})",
            ),
            apply=_make_apply(vampire),
            played_card_type=CARD_TYPE,
        )
        for vampire in eligible
    ]


def _provide_second_tradition_domain_block_candidate(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    player = context["player"]  # offered only to defender, see BLOCK_CANDIDATE_INJECTION_HOOK.
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    used_by = _used_by(context.get("pending"))
    eligible = _eligible_locked(state, player, used_by)
    if not eligible:
        return []

    def _make_apply(vampire: VampireInPlay) -> Any:
        def _apply(s: GameState) -> VampireInPlay:
            play_from_hand(s, player, KRCG_ID)
            vampire.blood -= BLOOD_COST
            vampire.locked = False
            used_by.add(vampire.instance_id)
            return vampire

        return _apply

    return [
        HookOption(
            choice=Choice(
                f"second_tradition_domain:unlock:{vampire.instance_id}",
                f"Second Tradition: Domain: burn 1 blood to unlock and block with "
                f"+{INTERCEPT_BONUS} intercept ({vampire.card.name})",
            ),
            apply=_make_apply(vampire),
            played_card_type=CARD_TYPE,
        )
        for vampire in eligible
    ]


hooks.register(INTERCEPT_MODIFIER_HOOK, _provide_second_tradition_domain_intercept)
hooks.register(BLOCK_CANDIDATE_INJECTION_HOOK, _provide_second_tradition_domain_block_candidate)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Second Tradition: Domain",
        status=Status.IMPLEMENTED,
        hooks=(Hook.INTERCEPT_MODIFIER, Hook.BLOCK_CANDIDATE_INJECTION),
        source=__name__,
    )
)
