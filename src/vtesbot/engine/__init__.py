"""Pure rules engine: state, phases, impulse/sequencing, actions, blocks,
combat, politics, torpor/diablerie (CLAUDE.md SS5).

No I/O, no printing, no network; all randomness via `GameState.rng`
(CLAUDE.md engine invariants).
"""

from . import hooks
from .agent import Agent
from .allies import RecruitAllySpec, burn_ally, detect_contest_on_recruit, recruit_ally
from .attachments import effective_capacity, effective_disciplines
from .cards import CardAttachment, CryptCard, LibraryCard
from .decision import Choice, Decision
from .errors import IllegalChoiceError, UnresolvedRulingError
from .format import FormatConfig
from .log import ReplayLog
from .observation import AllyView, Observation, VampireView, build_observation
from .ousting import check_oust
from .rng import GameRNG
from .setup import DeckSpec, setup_game
from .state import AllyInPlay, GameState, PlayerState, VampireInPlay

__all__ = [
    "Agent",
    "AllyInPlay",
    "RecruitAllySpec",
    "burn_ally",
    "detect_contest_on_recruit",
    "recruit_ally",
    "effective_capacity",
    "effective_disciplines",
    "CardAttachment",
    "CryptCard",
    "LibraryCard",
    "Choice",
    "Decision",
    "IllegalChoiceError",
    "UnresolvedRulingError",
    "FormatConfig",
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
