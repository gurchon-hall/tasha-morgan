"""The Sleeping Mind (Action Modifier). krcg id 101805. krcg's own
printed/sort name is "Sleeping Mind, The" (`name_variants == ["Sleeping
Mind, The", "Sleeping Mind"]`); `printed_name` is "The Sleeping Mind".

Card text (verbatim, via `krcg.load()` + `msgspec.json.encode()` in the
project's `uv run` virtualenv (krcg 5.14), 2026-10-15, matching the raw
snapshot saved to `data/cards/101805.json`):
    "Only usable as the action is announced.
    [dom] Choose a locked vampire. The chosen vampire cannot block this
    action.
    [DOM] During this action, minions cannot unlock."

Rulings (verbatim, via krcg; `cards["Sleeping Mind, The"].rulings`):
    - "[DOM] Does not prevent wake effects to be played (eg. {Wake with
      Evening's Freshness}), but does prevent unlock after action
      resolution (eg. {Freak Drive} or [ani] {Cats' Guidance})."
      [PIB 20150703]
    - "Must be played (as well as other 'as the action is announced'
      action modifiers) before action modifiers that are not explicitly
      played 'as the action is announced' (e.g., {Conditioning})."
      [ANK 20190425]
    - "Replace the action card (if any) before playing it."
      [ANK 20181208]

Card type: Action Modifier. `blood_cost == "1"` (burned by the playing
vampire); paid as `HookOption.cost` alongside `play_from_hand`, not
inside `apply()` -- see "Cost paid even if canceled" below. Legal since
1996-11-27; on the active 2P allowed list (`data/formats/2p/
2026-10-03.json`). Single 2P opponent: no prey/predator ambiguity.

Status: implemented for the basic clause only, against
`BLOCK_CANDIDATE_EXCLUSION_HOOK` (same mechanism as `cards/seduction.py`,
krcg 101712). Unlike Seduction, "a locked vampire" is explicitly the
target pool -- the opponent's `zone == "ready"` *and* `locked == True`
vampires (not `ready_unlocked_vampires`): naming a locked vampire here
specifically vetoes any later wake-based block attempt against it for the
rest of the action, per [PIB 20150703]'s own confirmation that a locked
vampire can still become a block candidate via a wake effect (e.g.
`cards/on_the_qui_vive.py` setting `woken = True`, which leaves `locked`
itself unchanged). The exclusion set is checked against the recomputed
candidate list on every retry of `attempt_block`'s loop (after
`WAKE_LOCKED_MINION_HOOK` has had its own chance to run), so this holds
regardless of how many times a wake is attempted against the same named
vampire.

The superior clause ("minions cannot unlock during this action") is
**not implemented**: it needs a generic "may this minion unlock right
now" gate checked by every `locked = False` call site, scoped to the
current action -- no card in this project's pool currently causes a
mid-action unlock (`locked = False` is only ever set from the unlock
phase, combat mend/press, diablerie, and contest resolution, none
reachable mid-action today), so that mechanism would be speculative. Only
the basic-clause provider is registered below.

Per-action cap (`rules-auditor` finding): Rulebook §2 Card Types,
verbatim: "A minion cannot play the same action modifier card more than
once during a single action (even if using a different Discipline
level)." Since `BLOCK_CANDIDATE_EXCLUSION_HOOK` is offered via
`hooks.offer_until_pass` (re-querying providers after every applied
option), two physical copies in hand previously let the actor exclude
two different locked defending vampires in one action.
`SLEEPING_MIND_PLAYED_KEY` (`context["pending"]`, mirrors
`voter_captivation.py`'s `GRANTED_KEY` convention) is a flag set the
moment the basic clause's own `apply` actually runs; the provider below
refuses to offer anything once it is set.

Cost paid even if canceled (OQ-38's companion ruling, `voter_captivation.py`'s
own precedent): both `play_from_hand` and the printed 1-blood burn are
`HookOption.cost` (paid unconditionally by `apply_chosen_option`, OQ-32),
not inside `apply` -- so a play canceled via `CANCEL_AS_PLAYED_HOOK` still
discards the physical card and burns the blood, but leaves
`SLEEPING_MIND_PLAYED_KEY`/the exclusion set untouched (both live only in
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

KRCG_ID = 101805
BASIC = "dom"
SUPERIOR = "DOM"
BLOOD_COST = 1
"""Printed `blood_cost == "1"` (module docstring)."""
CARD_TYPE = "Action Modifier"
SLEEPING_MIND_PLAYED_KEY = "sleeping_mind_played"
"""Module docstring's "Per-action cap": `context["pending"]` key set once
the basic clause's own `apply` has actually run this action."""


def _already_played(pending: dict[str, Any] | None) -> bool:
    return bool(pending) and pending.get(SLEEPING_MIND_PLAYED_KEY, False)


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


def _eligible_locked_targets(
    state: GameState, defender: str, pending: dict[str, Any] | None
) -> list[VampireInPlay]:
    """ "Choose a locked vampire" -- `zone == "ready"` and `locked == True`
    (module docstring; not `ready_unlocked_vampires`), minus any already
    excluded."""
    excluded = _already_excluded(pending)
    return [
        v
        for v in state.players[defender].vampires.values()
        if v.zone == "ready" and v.locked and v.instance_id not in excluded
    ]


def _provide_sleeping_mind_basic(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[dom] Choose a locked vampire. The chosen vampire cannot block
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
    if acting_vampire.blood < BLOOD_COST:
        return []  # printed blood cost: must have enough blood to play at all.
    defender = context["defender"]
    pending = context.get("pending")
    if _already_played(pending):
        return []  # per-action cap (module docstring): already played this action.
    eligible = _eligible_locked_targets(state, defender, pending)
    if not eligible:
        return []  # never offer a play that cannot resolve.

    def _cost(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        acting_vampire.blood -= BLOOD_COST

    def _apply(s: GameState) -> None:
        targets = _eligible_locked_targets(s, defender, pending)
        if len(targets) == 1:
            target = targets[0]
        else:
            choices = tuple(
                Choice(f"sleeping_mind_target:{v.instance_id}", f"Choose {v.card.name}")
                for v in targets
            )
            decision = Decision(player=player, kind="sleeping_mind_target", choices=choices)
            chosen_value = s.ask(decision).value
            target_id = chosen_value.split(":", 1)[1]
            target = s.players[defender].vampires[target_id]
        if pending is not None:
            pending.setdefault(PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY, set()).add(target.instance_id)
            pending[SLEEPING_MIND_PLAYED_KEY] = True

    return [
        HookOption(
            choice=Choice(
                "sleeping_mind:basic",
                "The Sleeping Mind [dom]: burn 1 blood, choose a locked vampire; cannot block",
            ),
            apply=_apply,
            cost=_cost,
            played_card_type=CARD_TYPE,
        )
    ]


hooks.register(BLOCK_CANDIDATE_EXCLUSION_HOOK, _provide_sleeping_mind_basic)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Sleeping Mind, The",
        status=Status.IMPLEMENTED,
        hooks=(Hook.BLOCK_CANDIDATE_EXCLUSION,),
        source=__name__,
    )
)
