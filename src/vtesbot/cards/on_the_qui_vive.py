"""On the Qui Vive (Reaction). krcg 101321. Snapshot: data/cards/101321.json
Offered only before a block attempt (ENG-030; other windows: ENG-060). Never offered
on an ally: allies neither block nor react here, so it would only cost a card."""

from vtesbot.cards.card import Card
from vtesbot.engine.hook_contexts import WakeLockedMinionContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101321

card = Card(KRCG_ID, "On the Qui Vive", "Reaction")


@card.on(Hook.WAKE_LOCKED_MINION)
def _wake(state: GameState, ctx: WakeLockedMinionContext) -> list[HookOption]:
    """Locked, not already woken, and none played since their unlock phase."""
    player = ctx["player"]
    if not card.in_hand(state, player):
        return []
    eligible = [
        v
        for v in state.players[player].vampires.values()
        if v.zone == "ready" and v.locked and not v.woken and not v.qui_vive_played_since_unlock
    ]
    options: list[HookOption] = []
    for vampire in eligible:

        def _apply(s: GameState, v: VampireInPlay = vampire) -> None:
            card.play_from_hand(s, player)
            v.woken = True
            v.qui_vive_played_since_unlock = True

        options.append(
            card.option(
                f"on_the_qui_vive:{vampire.instance_id}",
                f"On the Qui Vive: wake {vampire.card.name}",
                _apply,
            )
        )
    return options
