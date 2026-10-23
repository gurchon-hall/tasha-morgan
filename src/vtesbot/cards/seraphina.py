"""Seraphina (Vampire). krcg 201686. Snapshot: data/cards/201686.json
Blood for a vampire (ready or torpid), life for a ready ally, up to its cap;
retainers have no life here. Added on success only. See ENG-041."""

from typing import Any

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire
from vtesbot.engine.allies import add_life
from vtesbot.engine.attachments import effective_capacity
from vtesbot.engine.damage import add_blood
from vtesbot.engine.hook_contexts import ActionCardPlayContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.phases.minion import ActionCardSpec
from vtesbot.engine.state import AllyInPlay, GameState, VampireInPlay

KRCG_ID = 201686
SERAPHINA_STEALTH = 1
ADD_AMOUNT = 2
VAMPIRE_IN_PLAY_ZONES = ("ready", "torpor")
ALLY_IN_PLAY_ZONES = ("ready",)

card = Card(KRCG_ID, "Seraphina")


def _vampire_option(vampire: VampireInPlay) -> HookOption:
    name = vampire.card.name

    def _apply(s: GameState) -> ActionCardSpec:
        def resolve(_pending: dict[str, Any]) -> None:
            added = add_blood(s, vampire, ADD_AMOUNT)
            s.log.record_event(f"Seraphina adds {added} blood to {name}")

        return ActionCardSpec(base_stealth=SERAPHINA_STEALTH, directed=False, resolve=resolve)

    return card.option(
        f"seraphina:blood:{vampire.instance_id}", f"Seraphina: add 2 blood to {name}", _apply
    )


def _ally_option(ally: AllyInPlay) -> HookOption:
    name = ally.name

    def _apply(s: GameState) -> ActionCardSpec:
        def resolve(_pending: dict[str, Any]) -> None:
            added = add_life(ally, ADD_AMOUNT)
            s.log.record_event(f"Seraphina adds {added} life to {name}")

        return ActionCardSpec(base_stealth=SERAPHINA_STEALTH, directed=False, resolve=resolve)

    return card.option(
        f"seraphina:life:{ally.instance_id}", f"Seraphina: add 2 life to {name}", _apply
    )


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_seraphina(state: GameState, ctx: ActionCardPlayContext) -> list[HookOption]:
    """Never offered on a minion already at its cap."""
    player, seraphina = ctx["player"], context_vampire(state, ctx)
    if seraphina is None or seraphina.card.krcg_id != KRCG_ID:
        return []
    player_state = state.players[player]
    options = [
        _vampire_option(v)
        for v in player_state.vampires.values()
        if v.zone in VAMPIRE_IN_PLAY_ZONES and effective_capacity(state, v) - v.blood > 0
    ]
    options += [
        _ally_option(a)
        for a in player_state.allies.values()
        if a.zone in ALLY_IN_PLAY_ZONES and a.starting_life - a.life > 0
    ]
    return options
