"""Life in the City (Master). krcg 101104. Snapshot: data/cards/101104.json
Trifle. Any ready vampire is a target, either player's, locked or not; a full
one is a legal target that gains nothing (`add_blood` caps at capacity)."""

from vtesbot.cards.card import Card
from vtesbot.engine.damage import add_blood
from vtesbot.engine.hook_contexts import MasterPhasePlayContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101104

card = Card(KRCG_ID, "Life in the City", "Master")


@card.on(Hook.MASTER_PHASE_PLAY)
def _play(state: GameState, ctx: MasterPhasePlayContext) -> list[HookOption]:
    player = ctx["player"]
    if not card.in_hand(state, player):
        return []
    targets = [
        vampire
        for player_state in state.players.values()
        for vampire in player_state.vampires.values()
        if vampire.zone == "ready"
    ]
    options: list[HookOption] = []
    for vampire in targets:

        def _apply(s: GameState, vampire: VampireInPlay = vampire) -> bool:
            card.play_from_hand(s, player)
            add_blood(s, vampire, 1)
            return True  # trifle

        options.append(
            card.option(
                f"life_in_the_city:{vampire.instance_id}",
                f"Life in the City: add 1 blood to {vampire.card.name} ({vampire.controller})",
                _apply,
            )
        )
    return options
