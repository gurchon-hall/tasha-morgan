"""Generic course of a minion-phase action: announce -> block attempt -> resolve.

Source: Rulebook SS4 Minion Phase (per the `vtes-rules-reference` skill
condensed mapping):
  1. "Announce (all terms fixed now ...), lock the acting minion."
  2. "Block attempts: directed action -> only the targeted Methuselah may
     block; undirected -> prey first, then predator. In 2P the opponent is
     both. Block succeeds if intercept >= stealth. Stealth may be added only
     when needed ...; intercept only when needed .... Declining to block is
     final unless the target changes."
  3. "If unblocked -> pay cost, resolve. If blocked -> action card burned,
     cost not paid, blocker locks, combat."

2P structural consequence (CLAUDE.md SS3, settled core structural rule, not
OQ-1 which is scoped to card-text wording): with exactly two Methuselahs,
the sole opponent is simultaneously prey and predator. The rulebook's
"prey first, then predator" sequencing exists to give each of several
*different* Methuselahs a chance to block in turn; when both roles are held
by the same single Methuselah there is only one decision-maker and no new
information arrives between a hypothetical "as prey" and "as predator" ask,
so this implementation collapses both directed and undirected actions to a
single block-attempt decision offered to that one opponent.

Stealth/intercept hook wiring (`engine/hooks.py`): "Stealth may be added
only when needed (an ongoing block would succeed); intercept only when
needed (acting stealth exceeds it)" (Rulebook SS4 Minion Phase, per the
`vtes-rules-reference` skill condensed mapping) is a strict ping-pong, not
the general "both sides get a turn" impulse window: the *blocking*
Methuselah may add intercept only while the attempt is currently failing
(stealth > intercept); the *acting* Methuselah may add stealth only while
the attempt is currently succeeding (intercept >= stealth). `_duel_stealth_
intercept` below implements exactly that alternation via the
`"stealth_modifier"` / `"intercept_modifier"` hooks; with no providers
registered for either hook (no stealth/intercept library cards implemented
yet), each offer is empty and the loop terminates immediately at
(stealth=base_stealth, intercept=0) -- byte-for-byte the milestone-2 result,
so this wiring is pure scaffolding until a card registers against one of
these hooks.

Action discriminator (OQ-9, `docs/OPEN_QUESTIONS.md`): `attempt_block` /
`_duel_stealth_intercept` / `perform_minion_action` below thread an explicit
`action: str | None` (e.g. `ACTION_BLEED`, `ACTION_HUNT`, `ACTION_
RECRUIT_ALLY`, `ACTION_POLITICAL`) into the `"block_attempt"` decision's own
context and into the `"stealth_modifier"`/`"intercept_modifier"` hook
context, so a provider can gate itself on which minion action is in progress
(e.g. Bonding's superior clause, "[DOM] Cannot be used to increase the
stealth of a non-bleed action") instead of guessing from `base_stealth`'s
numeric value.

Pending scratch container (OQ-11, `docs/OPEN_QUESTIONS.md`):
`perform_minion_action` builds one shared, mutable `pending: dict[str, Any]`
per action attempt, threads it into the block-attempt phase's hook context
(so a stealth/intercept provider's `apply(state)` can stash something), and
hands that same object to `resolve`/`on_blocked` once the outcome is known,
so a single card play can deliver an effect that spans both phases without
desynchronizing from whatever later clamp/computation consumes it (see
`engine/phases/minion.py`'s own docstring for the worked example).
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from . import hooks
from .combat import run_combat
from .decision import Choice, Decision

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

STEALTH_MODIFIER_HOOK = "stealth_modifier"
INTERCEPT_MODIFIER_HOOK = "intercept_modifier"

ACTION_BLEED = "bleed"
ACTION_HUNT = "hunt"
ACTION_RECRUIT_ALLY = "recruit_ally"
ACTION_POLITICAL = "political_action"
"""Action-name discriminator constants (OQ-9, `docs/OPEN_QUESTIONS.md`): the
single source of truth for `action=` values passed to `attempt_block`/
`perform_minion_action`, so a producing call site (`engine/phases/minion.py`,
`engine/politics.py`) and a consuming hook provider cannot silently desync
over a re-typed literal."""


def _duel_stealth_intercept(
    state: GameState,
    actor: str,
    defender: str,
    base_stealth: int,
    acting_vampire: VampireInPlay | None,
    blocker: VampireInPlay,
    action: str | None = None,
    pending: dict[str, Any] | None = None,
) -> tuple[int, int]:
    """Resolve the "only when needed" stealth/intercept ping-pong for one
    block attempt against `blocker` (see module docstring)."""
    stealth = base_stealth
    intercept = 0
    context = {
        "actor": actor,
        "defender": defender,
        "acting_vampire": acting_vampire.instance_id if acting_vampire is not None else None,
        "blocking_vampire": blocker.instance_id,
        "action": action,
        "pending": pending,
    }
    while True:
        if stealth > intercept:
            # Block currently fails: intercept may be added, only now needed.
            options = hooks.offer(
                INTERCEPT_MODIFIER_HOOK,
                state,
                player=defender,
                stealth=stealth,
                intercept=intercept,
                **context,
            )
            if not options:
                return stealth, intercept
            delta = _ask_modifier(state, defender, INTERCEPT_MODIFIER_HOOK, options, context)
            if delta is None:
                return stealth, intercept
            intercept += delta
        else:
            # Block currently succeeds: stealth may be added, only now needed.
            options = hooks.offer(
                STEALTH_MODIFIER_HOOK,
                state,
                player=actor,
                stealth=stealth,
                intercept=intercept,
                **context,
            )
            if not options:
                return stealth, intercept
            delta = _ask_modifier(state, actor, STEALTH_MODIFIER_HOOK, options, context)
            if delta is None:
                return stealth, intercept
            stealth += delta


def _ask_modifier(
    state: GameState,
    player: str,
    hook_name: str,
    options: list[hooks.HookOption],
    context: dict,
) -> int | None:
    """Offer `options` plus a decline choice; return the applied delta, or
    None if the player declines (the hook's `apply` must return an `int`)."""
    by_value = {o.choice.value: o for o in options}
    choices = tuple(o.choice for o in options) + (Choice("decline", "Decline"),)
    decision = Decision(player=player, kind=hook_name, choices=choices, context=dict(context))
    answer = state.ask(decision)
    if answer.value == "decline":
        return None
    return by_value[answer.value].apply(state)


def attempt_block(
    state: GameState,
    actor: str,
    defender: str,
    base_stealth: int,
    acting_vampire: VampireInPlay | None = None,
    action: str | None = None,
    pending: dict[str, Any] | None = None,
) -> VampireInPlay | None:
    """Offer `defender` the chance to block with a ready, unlocked vampire.

    Returns the blocking vampire if a block *succeeds* (intercept >=
    stealth); returns None once the defender declines. Rulebook SS4: "If one
    attempt to block fails, another can be made as often as the blocking
    Methuselah wishes" -- a *failed* attempt (stealth exceeds intercept) does
    not end the block-attempt window and does not lock the failed vampire
    (see OQ-5 on that specific lock-timing reading); the defender is
    re-offered the choice of another candidate vampire or declining, looping
    until they decline or a block succeeds. This is the "three states: no
    current block attempt / ongoing block attempt / blocks declined by all"
    model named by the `vtes-rules-reference` skill.

    `action` (OQ-9) and `pending` (OQ-11, `docs/OPEN_QUESTIONS.md`) are
    forwarded into both the `"block_attempt"` decision's own context and the
    stealth/intercept hook context built by `_duel_stealth_intercept`; a
    caller that does not pass `pending` gets one fresh `{}`, created once
    here (not per retry of the loop below), so every hook offer during this
    one call shares the same mutable object.
    """
    if pending is None:
        pending = {}
    while True:
        candidates = state.ready_unlocked_vampires(defender)
        if not candidates:
            return None  # nothing legal to block with: no vacuous decision raised.

        choices = tuple(
            Choice(f"block_with:{v.instance_id}", f"Block with {v.card.name}") for v in candidates
        ) + (Choice("decline", "Decline to block"),)
        decision = Decision(
            player=defender,
            kind="block_attempt",
            choices=choices,
            context={"actor": actor, "base_stealth": base_stealth, "action": action},
        )
        choice = state.ask(decision)
        if choice.value == "decline":
            return None

        instance_id = choice.value.split(":", 1)[1]
        blocker = state.players[defender].vampires[instance_id]

        stealth, intercept = _duel_stealth_intercept(
            state, actor, defender, base_stealth, acting_vampire, blocker, action, pending
        )
        if intercept >= stealth:
            return blocker
        # Failed attempt: does not lock the blocker, does not end the
        # window -- loop back and re-offer another attempt or decline.


def perform_minion_action(
    state: GameState,
    actor_player: str,
    defender_player: str,
    vampire: VampireInPlay,
    base_stealth: int,
    resolve: Callable[[dict[str, Any]], None],
    action: str | None = None,
    on_blocked: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    """Announce (lock) -> block attempt -> resolve-or-combat (Rulebook SS4).

    `resolve` is called only if the action goes unblocked (declined or
    evaded); it must perform the action's own effect (e.g. bleed/hunt).
    `on_blocked`, if provided, is called only if the action is blocked,
    *after* combat resolves (Rulebook SS4 "Resolve the Action": "If the
    action is blocked, then ... the cost of the action is not paid" -- a
    card-specific consequence of a block, e.g. burning a card set aside at
    announce time); a call site that never passes it (e.g. bleed/hunt) sees
    no behaviour change on the blocked branch.

    `action` (OQ-9) and the per-attempt `pending: dict[str, Any]` scratch
    container (OQ-11, `docs/OPEN_QUESTIONS.md`) are threaded through to
    `attempt_block` and then on to `resolve`/`on_blocked`, so a card played
    during the earlier block-attempt phase can stash something for either
    callback to read back -- see `engine/phases/minion.py`'s own docstring
    for the worked example this resolves.
    """
    vampire.locked = True
    pending: dict[str, Any] = {}
    blocker = attempt_block(
        state, actor_player, defender_player, base_stealth, vampire, action=action, pending=pending
    )
    if blocker is not None:
        blocker.locked = True
        run_combat(state, actor_player, vampire, defender_player, blocker)
        if on_blocked is not None:
            on_blocked(pending)
        return
    resolve(pending)
