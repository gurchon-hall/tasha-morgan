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
the sole opponent is simultaneously prey and predator, so the rulebook's
"prey first, then predator" sequencing (meant to give several *different*
Methuselahs each a turn) collapses to a single block-attempt decision,
offered to that one opponent, for both directed and undirected actions.

Stealth/intercept ping-pong (`engine/hooks.py`): per the rule quoted above,
the *blocking* Methuselah may add intercept only while the attempt is
currently failing (stealth > intercept); the *acting* Methuselah may add
stealth only while it is currently succeeding (intercept >= stealth) --
this is a strict alternation, not the general "both sides get a turn"
impulse window. `_duel_stealth_intercept` below implements it via the
`"stealth_modifier"`/`"intercept_modifier"` hooks; with no providers
registered for either hook yet, each offer is empty and the loop terminates
immediately at (stealth=base_stealth, intercept=0).

Open-question plumbing threaded through `attempt_block`/
`_duel_stealth_intercept`/`perform_minion_action` below (`docs/
OPEN_QUESTIONS.md`; see each parameter's own docstring for how it is used):
- OQ-9: `action: str | None` (the `ACTION_*` constants below) lets a hook
  provider gate on which minion action is in progress (e.g. Bonding's
  "cannot be used to increase the stealth of a non-bleed action") instead of
  guessing from `base_stealth`'s numeric value.
- OQ-17: `directed: bool | None` records the Rulebook glossary's Directed
  vs. Undirected Action distinction; the 2P collapse above means it changes
  no mechanics here today, it is threaded through only as context for a
  future hook/decision consumer.
- OQ-11: `perform_minion_action` builds one shared mutable `pending:
  dict[str, Any]` per attempt so a card play spanning the block-attempt and
  resolve/on_blocked phases can carry state between them (see `engine/
  phases/minion.py` for the worked example).
- OQ-26 (resolved): `attempt_block` also offers `BLOCK_CANDIDATE_INJECTION_
  HOOK` to the defender each retry, so a provider can contribute a candidate
  built from one of the defender's own *locked* vampires (e.g. Organized
  Resistance). Per the controlling ruling [LSJ 20090514] such a block cannot
  fail once chosen, so it bypasses `_duel_stealth_intercept` entirely. With
  no provider registered, this is a no-op.
- OQ-25 (resolved): `perform_minion_action`'s `maneuver_grant` seeds one
  optional pre-combat maneuver grant into this function's own blocked-branch
  `run_combat` call (see `engine/combat.py`'s "Pre-combat grant seeding"
  section for the unblocked-path counterpart).
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from . import hooks
from .combat import run_combat, seed_pre_combat_maneuver_grant
from .decision import Choice, Decision

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

STEALTH_MODIFIER_HOOK = "stealth_modifier"
INTERCEPT_MODIFIER_HOOK = "intercept_modifier"
BLOCK_CANDIDATE_INJECTION_HOOK = "block_candidate_injection"
"""OQ-26 (`docs/OPEN_QUESTIONS.md`, resolved): mirrors `src/vtesbot/cards/
registry.py::Hook.BLOCK_CANDIDATE_INJECTION`'s own string value. See the
module docstring's OQ-26 entry for the mechanism; a provider's
`HookOption.apply(state)` must unlock its chosen (locked) vampire and
return it, for `attempt_block` to return directly as an unconditional
successful blocker."""

ACTION_BLEED = "bleed"
ACTION_HUNT = "hunt"
ACTION_RECRUIT_ALLY = "recruit_ally"
ACTION_POLITICAL = "political_action"
ACTION_ACTION_CARD = "action_card"
"""Action-name discriminator constants (OQ-9, `docs/OPEN_QUESTIONS.md`): the
single source of truth for `action=` values passed to `attempt_block`/
`perform_minion_action`, so a producing call site (`engine/phases/minion.py`,
`engine/politics.py`) and a consuming hook provider cannot silently desync
over a re-typed literal. `ACTION_ACTION_CARD` is the one fixed discriminator
every `"action_card_play"` hook play shares, regardless of which specific
library card of printed `types == ["Action"]` is being played."""


def _duel_stealth_intercept(
    state: GameState,
    actor: str,
    defender: str,
    base_stealth: int,
    acting_vampire: VampireInPlay | None,
    blocker: VampireInPlay,
    action: str | None = None,
    directed: bool | None = None,
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
        "directed": directed,
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
    directed: bool | None = None,
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

    `action` (OQ-9) and `directed` (OQ-17) are forwarded into the
    `"block_attempt"` decision's own context and the stealth/intercept hook
    context (see module docstring). `pending` (OQ-11) likewise; a caller that
    does not pass one gets a fresh `{}` created once here, so every hook
    offer during this call shares the same mutable object.

    `BLOCK_CANDIDATE_INJECTION_HOOK` (OQ-26, resolved, see module docstring)
    is offered to `defender` every time around the loop, alongside the
    hardcoded `state.ready_unlocked_vampires(defender)` candidates. With no
    provider registered, this adds nothing.
    """
    if pending is None:
        pending = {}
    while True:
        candidates = state.ready_unlocked_vampires(defender)
        candidate_choices = tuple(
            Choice(f"block_with:{v.instance_id}", f"Block with {v.card.name}") for v in candidates
        )

        injected_options = hooks.offer(
            BLOCK_CANDIDATE_INJECTION_HOOK,
            state,
            player=defender,
            actor=actor,
            defender=defender,
            acting_vampire=acting_vampire.instance_id if acting_vampire is not None else None,
            action=action,
            directed=directed,
            base_stealth=base_stealth,
            pending=pending,
        )
        by_injected_value = {o.choice.value: o for o in injected_options}

        offered_choices = candidate_choices + tuple(o.choice for o in injected_options)
        if not offered_choices:
            return None  # nothing legal to block with: no vacuous decision raised.

        choices = offered_choices + (Choice("decline", "Decline to block"),)
        hooks.ensure_unique_choice_values(choices, decision_kind="block_attempt")
        decision = Decision(
            player=defender,
            kind="block_attempt",
            choices=choices,
            context={
                "actor": actor,
                "base_stealth": base_stealth,
                "action": action,
                "directed": directed,
            },
        )
        choice = state.ask(decision)
        if choice.value == "decline":
            return None

        if choice.value in by_injected_value:
            # OQ-26: an immediate, unconditional successful block -- never
            # runs the stealth/intercept ping-pong for this candidate.
            return by_injected_value[choice.value].apply(state)

        instance_id = choice.value.split(":", 1)[1]
        blocker = state.players[defender].vampires[instance_id]

        stealth, intercept = _duel_stealth_intercept(
            state,
            actor,
            defender,
            base_stealth,
            acting_vampire,
            blocker,
            action=action,
            directed=directed,
            pending=pending,
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
    directed: bool | None = None,
    on_blocked: Callable[[dict[str, Any]], None] | None = None,
    maneuver_grant: str | None = None,
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

    `action` (OQ-9), `directed` (OQ-17) and the per-attempt `pending:
    dict[str, Any]` scratch container (OQ-11) are threaded through to
    `attempt_block` and then on to `resolve`/`on_blocked`, so a card played
    during the block-attempt phase can stash something for either callback
    to read back (see module docstring; worked example in `engine/phases/
    minion.py`).

    `maneuver_grant` (OQ-25, resolved): a vampire instance id to pre-grant
    one optional maneuver to, for the combat this *blocked* branch's own
    `run_combat` call produces (`None`, the default, changes nothing). This
    is the only way to reach that combat with a pre-seeded grant, since
    unlike the unblocked branch's `resolve()` callback, this function has no
    `ActionCardSpec`-shaped hook of its own to extend it -- see `engine/
    combat.py`'s "Pre-combat grant seeding" section.
    """
    vampire.locked = True
    pending: dict[str, Any] = {}
    blocker = attempt_block(
        state,
        actor_player,
        defender_player,
        base_stealth,
        vampire,
        action=action,
        directed=directed,
        pending=pending,
    )
    if blocker is not None:
        blocker.locked = True
        initial_combat_state = (
            seed_pre_combat_maneuver_grant(maneuver_grant) if maneuver_grant is not None else None
        )
        run_combat(state, actor_player, vampire, defender_player, blocker, initial_combat_state)
        if on_blocked is not None:
            on_blocked(pending)
        return
    resolve(pending)
