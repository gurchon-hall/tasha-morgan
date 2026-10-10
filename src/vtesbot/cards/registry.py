"""The card implementation registry.

CLAUDE.md SS6: "A card is implemented only when: effect code + test(s)
covering its text and each known ruling + registry entry + listed in the
active 2P list." The `implement-card` skill's step 6 ("Register") and the
`card-implementer` agent's output contract both name exactly two statuses,
`"implemented"` and `"blocked"` -- a card with neither is simply not yet
attempted (no registry entry at all; that is the normal, unremarkable state
for most of the pool after this scaffolding pass, not an error).

A card module (`src/vtesbot/cards/<snake_case_name>.py`) registers itself
once, at import time, by calling `register(CardRegistration(...))`;
`src/vtesbot/cards/__init__.py` imports every such module so the
registration side effect always runs before any code queries this registry
or `engine/hooks.py` (see `docs/DECISIONS.md` D-5 for why this is a static,
process-wide catalogue and not `GameState`).

`krcg_id` is the registry key (crypt vampire abilities and library cards
share the same krcg id space and the same registry -- a printed vampire
ability is exactly as much "a card" for this purpose as a library card,
CLAUDE.md SS5/SS6).
"""

from dataclasses import dataclass
from enum import StrEnum


class Status(StrEnum):
    IMPLEMENTED = "implemented"
    BLOCKED = "blocked"


class Hook(StrEnum):
    """Engine hook points a card's effect module may register against.

    Mirrors the hook names actually wired in `engine/hooks.py` call sites,
    plus a few named-but-not-yet-wired categories kept here purely for
    classification (CLAUDE.md milestone-3 scaffolding pass report) until a
    future rules-engineer pass builds their engine-side wiring.
    """

    # Wired this pass (engine/hooks.py has a real call site):
    MASTER_PHASE_PLAY = "master_phase_play"
    STEALTH_MODIFIER = "stealth_modifier"
    INTERCEPT_MODIFIER = "intercept_modifier"
    BLEED_AMOUNT_MODIFIER = "bleed_amount_modifier"
    BLEED_AMOUNT_FIXED_MODIFIER = "bleed_amount_fixed_modifier"
    DAMAGE_PREVENTION = "damage_prevention"
    COMBAT_STRIKE_OPTION = "combat_strike_option"
    COMBAT_STRENGTH_MODIFIER = "combat_strength_modifier"
    COMBAT_DODGE_OPTION = "combat_dodge_option"
    """A card/ability-granted dodge, offered alongside `COMBAT_STRIKE_OPTION`
    at the strike step (`engine/combat.py::_ask_strike`). Choosing it always
    deals 0 damage and zeroes whatever damage the opponent's simultaneous
    strike this round would otherwise deal to the dodging combatant
    (`engine/combat.py::_resolve_one_strike`/`_resolve_strike_pair`) --
    resolves `docs/OPEN_QUESTIONS.md` OQ-18 Gap 2."""
    COMBAT_ADDITIONAL_STRIKE = "combat_additional_strike"
    """A card/ability-granted extra strike this round, offered after the
    normal strike pair (and after each additional-strike pair) via
    `engine/combat.py::_ask_additional_strike`; using one re-enters the full
    strike-choice machinery (`COMBAT_STRIKE_OPTION`/`COMBAT_DODGE_OPTION`
    included) for that combatant's additional strike -- resolves
    `docs/OPEN_QUESTIONS.md` OQ-18 Gap 2."""
    CAPACITY_MODIFIER = "capacity_modifier"
    DISCIPLINE_LEVEL_MODIFIER = "discipline_level_modifier"
    RECRUIT_ALLY_PLAY = "recruit_ally_play"
    ACTION_CARD_PLAY = "action_card_play"
    """A library card of type "Action" (not "Action Modifier") that itself
    constitutes the acting minion's one action for the turn, distinct from
    `RECRUIT_ALLY_PLAY` (Ally-specific). Wired by `engine/phases/minion.py::
    ACTION_CARD_PLAY_HOOK` / `_perform_action_card`, generalizing the
    `RECRUIT_ALLY_PLAY` pattern beyond Allies -- see `docs/OPEN_QUESTIONS.md`
    OQ-17 (resolved)."""
    # Named for classification; no engine wiring exists yet (see the
    # rules-engineer milestone-3 scaffolding report for what each needs):
    POLITICAL_ACTION = "political_action"
    POLLING_STEP = "polling_step"
    MANEUVER = "maneuver"
    RANGED_STRIKE = "ranged_strike"
    ALLY_ENTITY = "ally_entity"
    LOCATION_ENTITY = "location_entity"
    HAND_SIZE_MODIFIER = "hand_size_modifier"
    DIABLERIE = "diablerie"
    CANCEL_AS_PLAYED = "cancel_as_played"
    BLOCK_CANDIDATE_INJECTION = "block_candidate_injection"
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
    """An `OQ-<n>` id (`docs/OPEN_QUESTIONS.md`) when `status is Status.BLOCKED`."""


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
