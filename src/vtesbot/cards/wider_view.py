"""Wider View (Master). krcg 102180. Snapshot: data/cards/102180.json
Trifle costing 1 pool (krcg `cost`). The crypt card just drawn can be the one
removed: drawing puts it in the uncontrolled region (Rulebook §8 Draw)."""

from vtesbot.cards.card import Card
from vtesbot.engine.damage import remove_vampire_from_game
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hook_contexts import InfluencePhaseActionContext, MasterPhasePlayContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.master_cards import bring_master_card_into_play
from vtesbot.engine.pool import can_afford_without_ousting, gain_pool, lose_pool
from vtesbot.engine.state import GameState, MasterCardInPlay, VampireInPlay

KRCG_ID = 102180
NAME = "Wider View"
POOL_COST = 1
BURN_TRANSFER_COST = 4
BURN_POOL_GAIN = 2

card = Card(KRCG_ID, NAME, "Master")


def _own_in_play_instances(state: GameState, player: str) -> list[MasterCardInPlay]:
    return [
        in_play
        for in_play in state.players[player].master_cards.values()
        if in_play.krcg_id == KRCG_ID and in_play.zone == "in_play"
    ]


@card.on(Hook.MASTER_PHASE_PLAY)
def _play(state: GameState, ctx: MasterPhasePlayContext) -> list[HookOption]:
    player = ctx["player"]
    if not card.in_hand(state, player):
        return []
    if not can_afford_without_ousting(state, player, POOL_COST):
        return []

    def _apply(s: GameState) -> bool:
        lose_pool(s, player, POOL_COST)
        card.play_from_hand(s, player)
        bring_master_card_into_play(s, player, krcg_id=KRCG_ID, name=NAME)
        return True  # trifle

    return [card.option("wider_view_play", f"Play {NAME} (1 pool)", _apply)]


@card.on(Hook.INFLUENCE_PHASE_ACTION)
def _draw_and_remove(state: GameState, ctx: InfluencePhaseActionContext) -> list[HookOption]:
    player = ctx["player"]
    if ctx["transfers_remaining"] < 1 or not _own_in_play_instances(state, player):
        return []
    if not state.players[player].crypt_deck:
        return []

    def _apply(s: GameState) -> int:
        p = s.players[player]
        drawn = p.crypt_deck.pop(0)
        instance_id = p.new_instance_id()
        p.vampires[instance_id] = VampireInPlay(
            instance_id=instance_id, card=drawn, controller=player, zone="uncontrolled"
        )
        candidates = [v for v in p.vampires.values() if v.zone == "uncontrolled"]
        if len(candidates) == 1:
            target = candidates[0]
        else:
            choices = tuple(
                Choice(
                    f"wider_view_remove_target:{v.instance_id}",
                    f"Remove {v.card.name} from the game",
                )
                for v in candidates
            )
            decision = Decision(player=player, kind="wider_view_remove_target", choices=choices)
            target = p.vampires[s.ask(decision).value.split(":", 1)[1]]
        remove_vampire_from_game(s, player, target)
        return 1

    return [
        card.option(
            "wider_view_draw_and_remove",
            f"{NAME}: draw and remove (1 transfer)",
            _apply,
            played_card_type=None,
        )
    ]


@card.on(Hook.INFLUENCE_PHASE_ACTION)
def _burn_for_pool(state: GameState, ctx: InfluencePhaseActionContext) -> list[HookOption]:
    player = ctx["player"]
    if ctx["transfers_remaining"] < BURN_TRANSFER_COST:
        return []
    options: list[HookOption] = []
    for in_play in _own_in_play_instances(state, player):

        def _apply(s: GameState, in_play: MasterCardInPlay = in_play) -> int:
            in_play.zone = "burned"
            in_play.locked = False
            gain_pool(s, player, BURN_POOL_GAIN)
            return BURN_TRANSFER_COST

        options.append(
            card.option(
                f"wider_view_burn_for_pool:{in_play.instance_id}",
                f"Burn {NAME} for {BURN_POOL_GAIN} pool ({BURN_TRANSFER_COST} transfers)",
                _apply,
                played_card_type=None,
            )
        )
    return options
