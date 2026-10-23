"""Sakhar (Vampire). krcg 201685. Snapshot: data/cards/201685.json
Her own action, no card played (ENG-011): the found card is named at announce
and moved on success. The text prints no shuffle, so none is done."""

from typing import Any

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire
from vtesbot.engine.cards import LibraryCard
from vtesbot.engine.hook_contexts import ActionCardPlayContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.phases.minion import ActionCardSpec
from vtesbot.engine.state import GameState

KRCG_ID = 201685
EQUIPMENT_CARD_TYPE = "Equipment"
SAKHAR_STEALTH = 1

card = Card(KRCG_ID, "Sakhar")


def _eligible_equipment_cards(state: GameState, player: str) -> list[LibraryCard]:
    return [c for c in state.players[player].library if c.card_type == EQUIPMENT_CARD_TYPE]


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_sakhar(state: GameState, ctx: ActionCardPlayContext) -> list[HookOption]:
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or vampire.card.krcg_id != KRCG_ID:
        return []
    options: list[HookOption] = []
    for index, equipment in enumerate(_eligible_equipment_cards(state, player)):
        krcg_id, name = equipment.krcg_id, equipment.name

        def _apply(s: GameState, krcg_id: int = krcg_id, name: str = name) -> ActionCardSpec:
            def resolve(_pending: dict[str, Any]) -> None:
                library = s.players[player].library
                for i, c in enumerate(library):
                    if (
                        c.card_type == EQUIPMENT_CARD_TYPE
                        and c.krcg_id == krcg_id
                        and c.name == name
                    ):
                        found = library.pop(i)
                        s.players[player].hand.append(found)
                        s.log.record_event(
                            f"{player} reveals {found.name} (Sakhar's search) and takes it to hand"
                        )
                        return
                # fizzles (RUL-007): the named card left the library

            return ActionCardSpec(base_stealth=SAKHAR_STEALTH, directed=False, resolve=resolve)

        options.append(
            card.option(
                f"sakhar:{index}:{krcg_id}", f"Sakhar: search your library for {name}", _apply
            )
        )
    return options
