"""Small lookups card modules keep needing (not itself a card)."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from vtesbot.cards._shared import bleed_bookkeeping as bleed_bookkeeping
from vtesbot.engine.attachments import effective_disciplines

if TYPE_CHECKING:
    from vtesbot.engine.state import GameState, VampireInPlay


def find_vampire(state: GameState, instance_id: str) -> VampireInPlay | None:
    """The vampire with `instance_id`, whichever player controls it."""
    for player_state in state.players.values():
        vampire = player_state.vampires.get(instance_id)
        if vampire is not None:
            return vampire
    return None


def context_vampire(state: GameState, ctx: Mapping[str, Any]) -> VampireInPlay | None:
    """`ctx["vampire"]` among `ctx["player"]`'s own vampires. Only for hooks
    where the asked player controls that vampire (strikes, own actions)."""
    return state.players[ctx["player"]].vampires.get(ctx["vampire"])


def acting_vampire(state: GameState, ctx: Mapping[str, Any]) -> VampireInPlay | None:
    """`ctx["acting_vampire"]` among `ctx["player"]`'s own vampires, for the
    block-attempt hooks offered to the actor; `None` when unset."""
    vampire_id = ctx["acting_vampire"]
    if vampire_id is None:
        return None
    return state.players[ctx["player"]].vampires.get(vampire_id)


def window_sides(ctx: Mapping[str, Any]) -> tuple[str, str, str]:
    """`(own vampire, opposing player, opposing vampire)` for `ctx["player"]`
    in a two-sided combat window (`BEFORE_RANGE`, `END_OF_ROUND`)."""
    if ctx["player"] == ctx["acting_player"]:
        return ctx["acting_vampire"], ctx["blocking_player"], ctx["blocking_vampire"]
    return ctx["blocking_vampire"], ctx["acting_player"], ctx["acting_vampire"]


def discipline_level(state: GameState, vampire: VampireInPlay, code: str) -> int:
    """Effective level of a discipline, printed or granted by an attachment
    (ENG-047): 0 none, 1 basic, 2 superior. `code` is the lowercase trigram."""
    if code != code.lower():
        raise ValueError(f"discipline code must be lowercase, got {code!r}")
    disciplines = effective_disciplines(state, vampire)
    return 2 if code.upper() in disciplines else 1 if code in disciplines else 0


def has_discipline(state: GameState, vampire: VampireInPlay, code: str) -> bool:
    """At least basic effective level of `code` (lowercase trigram)."""
    return discipline_level(state, vampire, code) >= 1
