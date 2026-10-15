"""Pure rules engine: state, phases, impulse, actions, blocks, combat,
politics, torpor/diablerie (CLAUDE.md §5). No I/O, no printing, no
network; all randomness via `GameState.rng`."""

from . import hooks
from .agent import Agent
from .allies import RecruitAllySpec, burn_ally, detect_contest_on_recruit, recruit_ally
from .attachments import (
    attach_card,
    detect_contest_on_attach,
    effective_capacity,
    effective_disciplines,
    find_attachment_by_instance_id,
    iter_attachments,
)
from .cards import (
    CardAttachment,
    CryptCard,
    DisciplineRequirement,
    DisciplineRequirementType,
    LibraryCard,
    Sect,
    derive_sect,
    requires_discipline,
)
from .decision import Choice, Decision
from .errors import IllegalChoiceError, UnresolvedRulingError
from .format import FormatConfig
from .hand import effective_hand_size, reconcile_hand_size
from .log import ReplayLog
from .master_cards import bring_master_card_into_play, detect_contest_on_bring_into_play
from .observation import AllyView, MasterCardView, Observation, VampireView, build_observation
from .ousting import check_oust
from .rng import GameRNG
from .setup import DeckSpec, setup_game
from .state import AllyInPlay, GameState, MasterCardInPlay, PlayerState, VampireInPlay

__all__ = [
    "Agent",
    "AllyInPlay",
    "RecruitAllySpec",
    "burn_ally",
    "detect_contest_on_recruit",
    "recruit_ally",
    "attach_card",
    "detect_contest_on_attach",
    "effective_capacity",
    "effective_disciplines",
    "find_attachment_by_instance_id",
    "iter_attachments",
    "bring_master_card_into_play",
    "detect_contest_on_bring_into_play",
    "MasterCardInPlay",
    "MasterCardView",
    "CardAttachment",
    "CryptCard",
    "DisciplineRequirement",
    "DisciplineRequirementType",
    "LibraryCard",
    "Sect",
    "derive_sect",
    "requires_discipline",
    "Choice",
    "Decision",
    "IllegalChoiceError",
    "UnresolvedRulingError",
    "FormatConfig",
    "effective_hand_size",
    "reconcile_hand_size",
    "ReplayLog",
    "Observation",
    "VampireView",
    "AllyView",
    "build_observation",
    "check_oust",
    "GameRNG",
    "DeckSpec",
    "setup_game",
    "GameState",
    "PlayerState",
    "VampireInPlay",
    "hooks",
]
