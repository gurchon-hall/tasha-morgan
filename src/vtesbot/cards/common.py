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
