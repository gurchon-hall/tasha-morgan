"""Seduction (Action Modifier). krcg id 101712.

Card text (verbatim, via `krcg.load()` + `msgspec.json.encode()` in the
project's `uv run` virtualenv (krcg 5.14), 2026-10-15, matching the raw
snapshot saved to `data/cards/101712.json`):
    "Only usable as the action is announced.
    [dom] Choose a younger vampire. The chosen vampire cannot block this
    action.
    [DOM] As above, but choose any vampire."

Rulings (verbatim, via krcg; `cards["Seduction"].rulings`):
    - "Must be played (as well as other 'as the action is announced'
      action modifiers) before action modifiers that are not explicitly
      played 'as the action is announced' (e.g., {Conditioning})."
      [ANK 20190425]
    - "Replace the action card (if any) before playing it."
      [ANK 20181208]

Card type: Action Modifier. `discipline_requirement == {"type": "Mono",
"disciplines": ["dom"]}`; superior Dominate widens "a younger vampire" to
"any vampire" (Rulebook §3). `cost is None` (free). Legal since
1994-09-15; on the active 2P allowed list (`data/formats/2p/
2026-10-03.json`). Single 2P opponent: no prey/predator ambiguity.

Status: implemented, against `BLOCK_CANDIDATE_EXCLUSION_HOOK` (`engine/
action.py`), offered to the acting player in `attempt_block`'s proactive
slot before the defender's candidate list is computed -- exactly "as the
action is announced". The target pool is the defender's *current block
candidates* (`state.ready_unlocked_vampires`, minus any already
excluded): a vampire that could not block anyway makes excluding it a
vacuous choice (enchant_kindred.py's "never offer a play that cannot
resolve" convention). "Younger" (basic clause) uses the OQ-17 convention
(archived, resolved): strictly lower printed `capacity` than the acting
vampire. Both on-file rulings describe play-order sequencing among
different cards' own windows, already satisfied by construction (this
hook fires before the stealth/intercept ping-pong where a non-"as
announced" modifier like Conditioning would be offered); neither needs
code of its own.

Target choice mirrors `fleetness.py`'s own announce-time binding: the
`HookOption` offered at the exclusion hook is a single "play Seduction"
choice; with exactly one eligible target its own `apply` binds directly,
with more than one it raises a nested `Decision`.

Per-action cap (`rules-auditor` finding): Rulebook §2 Card Types,
verbatim: "A minion cannot play the same action modifier card more than
once during a single action (even if using a different Discipline
level)." Since `BLOCK_CANDIDATE_EXCLUSION_HOOK` is offered via
`hooks.offer_until_pass` (re-querying providers after every applied
option), two physical copies in hand previously let the actor exclude
two different defending vampires in one action. `SEDUCTION_PLAYED_KEY`
(`context["pending"]`, mirrors `voter_captivation.py`'s `GRANTED_KEY`
convention) is a flag set the moment either clause's own `apply` actually
runs; both providers below refuse to offer anything once it is set,
shared between the basic and superior clauses per the rulebook's own
"even if using a different Discipline level" clause -- one play of
either trips both.

Cost paid even if canceled (OQ-38's companion ruling, `voter_captivation.py`'s
own precedent): `play_from_hand` is `HookOption.cost` (paid unconditionally
by `apply_chosen_option`, OQ-32), not inside `apply` -- so a play canceled
via `CANCEL_AS_PLAYED_HOOK` still discards the physical card but leaves
`SEDUCTION_PLAYED_KEY`/the exclusion set untouched (both live only in
`apply`, which a cancellation suppresses), matching the ruling that a
canceled attempt does not itself trigger the once-per-action limit. No
provider in this pool currently cancels this hook; this keeps the same
landmine `voter_captivation.py`'s own docstring already names (OQ-32) from
reopening here.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import (
    BLOCK_CANDIDATE_EXCLUSION_HOOK,
    PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY,
)
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101712
BASIC = "dom"
SUPERIOR = "DOM"
CARD_TYPE = "Action Modifier"
"""`HookOption.played_card_type` (OQ-33): matches this module's own "Card
type: Action Modifier" docstring fact above."""
SEDUCTION_PLAYED_KEY = "seduction_played"
"""Module docstring's "Per-action cap": `context["pending"]` key set once
either clause's own `apply` has actually run this action."""


def _already_played(pending: dict[str, Any] | None) -> bool:
    return bool(pending) and pending.get(SEDUCTION_PLAYED_KEY, False)


def _acting_vampire(state: GameState, context: Mapping[str, Any]) -> VampireInPlay | None:
    player = context["player"]
    vampire_id = context.get("acting_vampire")
    if vampire_id is None:
        return None
    return state.players[player].vampires.get(vampire_id)


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _already_excluded(pending: dict[str, Any] | None) -> set[str]:
    if pending is None:
        return set()
    return pending.get(PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY, set())


def _eligible_targets(
    state: GameState,
    defender: str,
    pending: dict[str, Any] | None,
    *,
    acting_vampire: VampireInPlay,
    require_younger: bool,
) -> list[VampireInPlay]:
    """The defender's current block candidates (module docstring), minus
    any already excluded; "younger" (basic clause) additionally filters to
    strictly lower printed capacity (OQ-17 convention)."""
    excluded = _already_excluded(pending)
    candidates = [
        v for v in state.ready_unlocked_vampires(defender) if v.instance_id not in excluded
    ]
    if require_younger:
        candidates = [v for v in candidates if v.card.capacity < acting_vampire.card.capacity]
    return candidates


def _make_cost(player: str) -> Any:
    def _cost(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)

    return _cost


def _make_apply(
    player: str,
    defender: str,
    pending: dict[str, Any] | None,
    acting_vampire: VampireInPlay,
    *,
    require_younger: bool,
) -> Any:
    def _apply(s: GameState) -> None:
        targets = _eligible_targets(
            s, defender, pending, acting_vampire=acting_vampire, require_younger=require_younger
        )
        if len(targets) == 1:
            target = targets[0]
        else:
            choices = tuple(
                Choice(f"seduction_target:{v.instance_id}", f"Choose {v.card.name}")
                for v in targets
            )
            decision = Decision(player=player, kind="seduction_target", choices=choices)
            chosen_value = s.ask(decision).value
            target_id = chosen_value.split(":", 1)[1]
            target = s.players[defender].vampires[target_id]
        if pending is not None:
            pending.setdefault(PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY, set()).add(target.instance_id)
            pending[SEDUCTION_PLAYED_KEY] = True

    return _apply


def _provide_seduction_basic(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[dom] Choose a younger vampire. The chosen vampire cannot block
    this action." """
    player = context["player"]
    acting_vampire = _acting_vampire(state, context)
    if acting_vampire is None:
        return []
    disciplines = acting_vampire.card.disciplines
    if BASIC not in disciplines and SUPERIOR not in disciplines:
        return []
    if not _has_card_in_hand(state, player):
        return []
    defender = context["defender"]
    pending = context.get("pending")
    if _already_played(pending):
        return []  # per-action cap (module docstring): already played this action.
    eligible = _eligible_targets(
        state, defender, pending, acting_vampire=acting_vampire, require_younger=True
    )
    if not eligible:
        return []  # never offer a play that cannot resolve.

    return [
        HookOption(
            choice=Choice(
                "seduction:basic", "Seduction [dom]: choose a younger vampire; cannot block"
            ),
            apply=_make_apply(player, defender, pending, acting_vampire, require_younger=True),
            cost=_make_cost(player),
            played_card_type=CARD_TYPE,
        )
    ]


def _provide_seduction_superior(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[DOM] As above, but choose any vampire." """
    player = context["player"]
    acting_vampire = _acting_vampire(state, context)
    if acting_vampire is None:
        return []
    if SUPERIOR not in acting_vampire.card.disciplines:
        return []
    if not _has_card_in_hand(state, player):
        return []
    defender = context["defender"]
    pending = context.get("pending")
    if _already_played(pending):
        return []  # per-action cap (module docstring): already played this action.
    eligible = _eligible_targets(
        state, defender, pending, acting_vampire=acting_vampire, require_younger=False
    )
    if not eligible:
        return []  # never offer a play that cannot resolve.

    return [
        HookOption(
            choice=Choice(
                "seduction:superior", "Seduction [DOM]: choose any vampire; cannot block"
            ),
            apply=_make_apply(player, defender, pending, acting_vampire, require_younger=False),
            cost=_make_cost(player),
            played_card_type=CARD_TYPE,
        )
    ]


hooks.register(BLOCK_CANDIDATE_EXCLUSION_HOOK, _provide_seduction_basic)
hooks.register(BLOCK_CANDIDATE_EXCLUSION_HOOK, _provide_seduction_superior)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Seduction",
        status=Status.IMPLEMENTED,
        hooks=(Hook.BLOCK_CANDIDATE_EXCLUSION,),
        source=__name__,
    )
)
