"""Engine-level errors. No-guessing rule (CLAUDE.md §2): an unsettled situation raises
`UnresolvedRulingError` and is recorded in `docs/OPEN_QUESTIONS.md` under its `OQ-<n>`."""


class UnresolvedRulingError(Exception):
    """Raised instead of guessing a rule the sources don't settle. `oq_id` is the
    `docs/OPEN_QUESTIONS.md` entry id; `detail` describes the situation."""

    def __init__(self, oq_id: str, detail: str = "") -> None:
        message = (
            f"Unresolved ruling ({oq_id}): {detail}" if detail else f"Unresolved ruling ({oq_id})"
        )
        super().__init__(message)
        self.oq_id = oq_id
        self.detail = detail


class IllegalChoiceError(Exception):
    """Raised when an agent picks a choice not among `decision.choices` -- enforces
    CLAUDE.md's "legality by construction" invariant."""


class GameOverError(Exception):
    """Raised by `GameState.ask` if a decision is requested after the game ended (§5
    Ending the Game). Safety net: phase loops must return once `state.game_over` is set."""
