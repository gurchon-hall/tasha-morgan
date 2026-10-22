"""Card implementation registry (CLAUDE.md §6): a module registers itself
at import via `register(CardRegistration(...))`. `krcg_id` is the key
(DES-005: static catalogue, not GameState).
"""

from dataclasses import dataclass
from enum import StrEnum


class Status(StrEnum):
    IMPLEMENTED = "implemented"
    BLOCKED = "blocked"


class Hook(StrEnum):
    """Engine hook points a card's effect module may register against.
    Mirrors names wired in `engine/hooks.py`; a few are named-but-unwired,
    kept for classification until engine-side wiring exists."""

    # Wired this pass (engine/hooks.py has a real call site):
    MASTER_PHASE_PLAY = "master_phase_play"
    MASTER_PHASE_ABILITY = "master_phase_ability"
    """A crypt card's own printed "during your master phase" ability
    (`engine/phases/master.py::MASTER_PHASE_ABILITY_HOOK`): offered
    alongside `MASTER_PHASE_PLAY` every iteration, but drawn from neither
    `actions_remaining` nor the trifle bonus (e.g. Lucinde, Alastor)."""
    INFLUENCE_PHASE_ACTION = "influence_phase_action"
    """A card-sourced, transfer-costed option offered during the Influence
    phase alongside the three hardcoded transfer types (ENG-016).
    `apply(state)` returns the `int` transfers consumed."""
    STEALTH_MODIFIER = "stealth_modifier"
    INTERCEPT_MODIFIER = "intercept_modifier"
    INTERCEPT_DECREASE = "intercept_decrease"
    """Acting-side Action Modifier reducing a blocking candidate's
    intercept, offered proactively and reactively (ENG-021/RUL-009). Appends
    an `ActiveInterceptDecrease` to `pending`; return ignored."""
    STEALTH_INCREASE = "stealth_increase"
    """`INTERCEPT_DECREASE`'s sibling for the acting side's stealth
    (RUL-011, Loup). Appends an `ActiveStealthIncrease` to `pending`; no
    `qualifies` predicate needed."""
    WAKE_LOCKED_MINION = "wake_locked_minion"
    """Defender-side sibling of `INTERCEPT_DECREASE`/`STEALTH_INCREASE`,
    offered to `defender` only (ENG-030). Sets `woken=True` on a locked
    vampire, or `AllyInPlay.skip_next_unlock` for an ally."""
    FORCE_BLOCK_ATTEMPT_FAILURE = "force_block_attempt_failure"
    """Acting-side sibling of `INTERCEPT_DECREASE`/`STEALTH_INCREASE`, offered
    only reactively once a block candidate is fixed (ENG-045). Forces the
    current block attempt to fail outright, bypassing the stealth/intercept
    comparison entirely -- distinct from an extreme `INTERCEPT_DECREASE`
    delta, which would still let the defender respond. Built for Forced
    Confessional (krcg 102250)."""
    BLEED_AMOUNT_MODIFIER = "bleed_amount_modifier"
    BLEED_AMOUNT_FIXED_MODIFIER = "bleed_amount_fixed_modifier"
    DAMAGE_PREVENTION = "damage_prevention"
    COMBAT_STRIKE_OPTION = "combat_strike_option"
    COMBAT_STRENGTH_MODIFIER = "combat_strength_modifier"
    COMBAT_DODGE_OPTION = "combat_dodge_option"
    """A card/ability-granted dodge, offered alongside `COMBAT_STRIKE_OPTION`
    at the strike step. Always deals 0 damage and zeroes the opponent's
    simultaneous strike this round (ENG-012 Gap 2)."""
    COMBAT_ADDITIONAL_STRIKE = "combat_additional_strike"
    """A card/ability-granted extra strike this round, offered after the
    normal strike pair; using one re-enters the full strike-choice
    machinery for that combatant's additional strike (ENG-012 Gap 2)."""
    CAPACITY_MODIFIER = "capacity_modifier"
    DISCIPLINE_LEVEL_MODIFIER = "discipline_level_modifier"
    HAND_SIZE_MODIFIER = "hand_size_modifier"
    """Passive mandatory numeric hook (`hooks.sum_modifiers`), wired by
    `effective_hand_size`. Contributes a signed delta to base hand size,
    re-checked every call (e.g. Carmelita Neillson)."""
    RECRUIT_ALLY_PLAY = "recruit_ally_play"
    ACTION_CARD_PLAY = "action_card_play"
    """A library card of type Action (not Action Modifier) that is itself
    the acting minion's whole action, distinct from `RECRUIT_ALLY_PLAY`.
    Generalizes that pattern beyond Allies (ENG-011)."""
    ATTACHMENT_REMOVAL_ACTION_PLAY = "attachment_removal_action_play"
    """Generic cumulative "+1 stealth action, by either side's vampires,
    removes a named attachment once N total contributions are made" minion
    action (`engine/phases/minion.py::build_attachment_removal_action_spec`),
    offered alongside `ACTION_CARD_PLAY`/`RECRUIT_ALLY_PLAY` (Pulled Fangs,
    krcg 101515)."""
    CANNOT_HUNT = "cannot_hunt"
    """Passive boolean hook (`hooks.any_true`): an attachment's mandatory
    "cannot hunt" clause, checked by `minion_phase`'s own mandatory-hunt
    loop before `_perform_hunt` (Pulled Fangs, krcg 101515)."""
    REFERENDUM_TALLIED = "referendum_tallied"
    """Mandatory per-provider reaction fired once a referendum's votes are
    tallied, before pass/fail effects. Hook site for Marcos Belegrad's
    pool burn (RUL-005); no provider registered yet."""
    VAMPIRE_ENTERS_TORPOR = "vampire_enters_torpor"
    """Mandatory per-provider reaction fired the instant a vampire's zone
    flips to torpor (`send_to_torpor`). Added for Fame's torpor pool-burn
    clause (ENG-014)."""
    UNLOCK_PHASE_MANDATORY_EFFECT = "unlock_phase_mandatory_effect"
    """Mandatory-but-orderable `hooks.offer`-style reaction, queried once
    per iteration of `unlock_phase`'s own pay-or-yield/Edge-gain ordering
    loop and folded into that same player-chosen order (not run first,
    unconditionally) -- added for Fame's unlock-phase pool-burn clause
    (ENG-014), per its own on-file ruling that such a payment "can be
    ordered with other unlock effects"."""
    MANEUVER = "maneuver"
    """A card/ability-granted maneuver, offered during Determine Range,
    acting side first, alternating, closing on two declines (RUL-008/ENG-019).
    A bundled strike must call `commit_strike_for_round`."""
    END_OF_ROUND = "end_of_round"
    """End of Round hook (Rulebook §4 Combat step 7), dispatched once per
    round on every exit path; two-sided impulse window, acting side first
    (RUL-002). Added for Taste of Vitae (ENG-020)."""
    BEFORE_RANGE = "before_range"
    """Before Range hook (Rulebook §4 Combat step 1), offered once per
    combat before round 1's Determine Range; two-sided impulse window,
    acting side first (RUL-002/ENG-029)."""
    ACTION_SUCCEEDED = "action_succeeded"
    """Mandatory per-provider reaction fired once an unblocked minion
    action's `resolve()` returns, regardless of its own effect (ENG-024,
    Loup). Context carries `actor_player`, `vampire`, `action`."""
    CANCEL_AS_PLAYED = "cancel_as_played"
    """Generic "cancel a card as played" hook (ENG-022), offered to the
    non-choosing side right after a `HookOption` is chosen, before its
    `apply` runs; the original `cost` has already run regardless."""
    # Named for classification; no engine wiring exists yet (see the
    # rules-engineer milestone-3 scaffolding report for what each needs):
    POLITICAL_ACTION = "political_action"
    POLLING_STEP = "polling_step"
    """Wired in `engine/politics.py` (RUL-005): a before-cast window before
    casting, and (ENG-027) a mid-cast window merged into vote-casting for
    retroactive cancellation. Return contract differs per phase."""
    REFERENDUM_RESOLVED = "referendum_resolved"
    """Fires strictly after a referendum fully resolves, including
    blocked-attempt combat; distinct from `POLLING_STEP`/
    `REFERENDUM_TALLIED` (ENG-026). Two-sided window, only for a passed
    political action."""
    VOTE_SOURCE_CAST_BONUS = "vote_source_cast_bonus"
    """Passive mandatory numeric hook, dispatched the instant a specific
    `VoteSource` is cast, after its own cast-time side effects (ENG-031,
    Fiorenza Savona). Returned `int` folds into that cast's own total."""
    RANGED_STRIKE = "ranged_strike"
    ALLY_ENTITY = "ally_entity"
    LOCATION_ENTITY = "location_entity"
    """Disputed Territory's "location" concept (ENG-025): not a new entity
    type, but two control-transfer primitives over attachment/master-card
    shapes. Implemented against the master-card primitive only."""
    DIABLERIE = "diablerie"
    BLOCK_CANDIDATE_INJECTION = "block_candidate_injection"
    BLOCK_CANDIDATE_EXCLUSION = "block_candidate_exclusion"
    """Subtractive sibling of `BLOCK_CANDIDATE_INJECTION`: offered to the
    actor proactively in `attempt_block`'s retry loop, before the
    defender's own candidate list is computed (`cards/seduction.py`,
    `cards/sleeping_mind.py`)."""
    BLOCK_ATTEMPT_COST = "block_attempt_cost"
    """Passive, per-candidate mandatory cost gate (`engine/action.py::
    BlockAttemptCost`/`BLOCK_ATTEMPT_COST_HOOK`): a crypt card's own passive
    ability, applying across every action type it ever performs, not one
    action card's own printed text. Distinct from `block_candidate_
    predicate` (an `ActionCardSpec` field, no `Hook` entry of its own since
    it is supplied per-action, not registered globally). A candidate that
    cannot afford an applicable cost is not offered at all; one that can
    pays it the instant it is chosen to attempt (Sergio Bueno, krcg
    201662)."""
    EQUIPMENT_ATTACHMENT = "equipment_attachment"


@dataclass(frozen=True)
class CardRegistration:
    krcg_id: int
    name: str
    status: Status
    hooks: tuple[Hook, ...]
    source: str
    """Short provenance note: the module path, or (for a card not yet
    implemented) a one-line description of what blocks it."""
    blocked_reason: str | None = None
    """A `RUL-<nnn>`/`ENG-<nnn>` id when `status is Status.BLOCKED` and a
    `docs/` entry is the blocker; otherwise a short
    descriptive string citing the missing engine data field or subsystem
    (not a ruling ambiguity -- see e.g. Queen Anne/Alexa Draper)."""


_REGISTRY: dict[int, CardRegistration] = {}


def register(reg: CardRegistration) -> CardRegistration:
    if reg.krcg_id in _REGISTRY:
        raise ValueError(f"card {reg.krcg_id} ({reg.name!r}) is already registered")
    if reg.status is Status.BLOCKED and not reg.blocked_reason:
        raise ValueError(f"card {reg.krcg_id} ({reg.name!r}) is blocked but has no blocked_reason")
    _REGISTRY[reg.krcg_id] = reg
    return reg


def get(krcg_id: int) -> CardRegistration | None:
    return _REGISTRY.get(krcg_id)


def all_registrations() -> tuple[CardRegistration, ...]:
    return tuple(_REGISTRY.values())


def implemented_ids() -> frozenset[int]:
    return frozenset(r.krcg_id for r in _REGISTRY.values() if r.status is Status.IMPLEMENTED)


def blocked_ids() -> frozenset[int]:
    return frozenset(r.krcg_id for r in _REGISTRY.values() if r.status is Status.BLOCKED)


def remove(krcg_id: int) -> None:
    """Test isolation helper only; production code never calls this."""
    _REGISTRY.pop(krcg_id, None)


def clear() -> None:
    """Test isolation helper only; production code never calls this."""
    _REGISTRY.clear()
