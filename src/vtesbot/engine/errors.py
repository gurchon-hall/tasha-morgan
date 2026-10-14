"""Engine-level errors.

No-guessing rule (CLAUDE.md SS2): whenever the official sources (card text >
rulings > 2P variant > rulebook) do not settle a situation, the engine must
not silently pick a behaviour. The code path raises `UnresolvedRulingError`
instead, and the situation is recorded in `docs/OPEN_QUESTIONS.md` under an
`OQ-<n>` id referenced by the error message.
"""


class UnresolvedRulingError(Exception):
    """Raised instead of guessing a rule or card interaction the sources do not settle.

    Args:
        oq_id: the `docs/OPEN_QUESTIONS.md` entry id (e.g. "OQ-1") describing the gap.
        detail: a short, specific description of the situation encountered.
    """

    def __init__(self, oq_id: str, detail: str = "") -> None:
        message = (
            f"Unresolved ruling ({oq_id}): {detail}" if detail else f"Unresolved ruling ({oq_id})"
        )
        super().__init__(message)
        self.oq_id = oq_id
        self.detail = detail


class IllegalChoiceError(Exception):
    """Raised when an agent returns a choice that is not among `decision.choices`.

    This is the engine-side enforcement of CLAUDE.md's "legality by
    construction" invariant: agents may only ever pick from the offered list.
    """


class GameOverError(Exception):
    """Raised by `GameState.ask` if a decision is requested after the game ended.

    Rulebook SS5 Ending the Game: "The game continues until only one
    Methuselah is left"; in a 2P duel (each is the other's prey, CLAUDE.md
    SS3) any oust leaves one, so no further player decision may be solicited.
    Phase loops must return once `state.game_over` is set; this is only the safety net behind that.
    """
