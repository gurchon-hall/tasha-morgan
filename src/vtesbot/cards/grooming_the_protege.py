"""Grooming the Protégé (Master). krcg 100860. Snapshot: data/cards/100860.json
"Younger" is a lower printed capacity (Rulebook §8 Capacity: "also a relative
measure of the vampire's age"); each amount from 1 up is its own choice."""

from vtesbot.cards.card import Card
from vtesbot.engine import effective_capacity
from vtesbot.engine.damage import add_blood
from vtesbot.engine.hook_contexts import MasterPhasePlayContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, PlayerState, VampireInPlay

KRCG_ID = 100860
MAX_BLOOD = 3

card = Card(KRCG_ID, "Grooming the Protégé", "Master")


def _sources(player_state: PlayerState) -> list[VampireInPlay]:
    return [v for v in player_state.vampires.values() if v.zone == "ready" and v.blood > 0]


def _targets(player_state: PlayerState, source: VampireInPlay) -> list[VampireInPlay]:
    return [
        v
        for v in player_state.vampires.values()
        if v.zone == "uncontrolled"
        and v.card.clan == source.card.clan
        and v.card.capacity < source.card.capacity
    ]


@card.on(Hook.MASTER_PHASE_PLAY)
def _play(state: GameState, ctx: MasterPhasePlayContext) -> list[HookOption]:
    player = ctx["player"]
    if not card.in_hand(state, player):
        return []
    player_state = state.players[player]
    options: list[HookOption] = []
    for source in _sources(player_state):
        for target in _targets(player_state, source):
            room = effective_capacity(state, target) - target.blood
            for amount in range(1, min(MAX_BLOOD, source.blood, room) + 1):

                def _apply(
                    s: GameState,
                    source: VampireInPlay = source,
                    target: VampireInPlay = target,
                    amount: int = amount,
                ) -> bool:
                    card.play_from_hand(s, player)
                    source.blood -= amount
                    add_blood(s, target, amount)
                    return False  # not a trifle

                options.append(
                    card.option(
                        f"grooming_the_protege:{source.instance_id}:{target.instance_id}:{amount}",
                        f"Grooming the Protégé: move {amount} blood from "
                        f"{source.card.name} to {target.card.name}",
                        _apply,
                    )
                )
    return options
