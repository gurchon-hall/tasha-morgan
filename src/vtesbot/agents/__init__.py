"""Player interface implementations (CLAUDE.md SS5): random-legal first,
heuristic and search-based later milestones.
"""

from .heuristic import HeuristicAgent
from .random_legal import RandomLegalAgent

__all__ = ["HeuristicAgent", "RandomLegalAgent"]
