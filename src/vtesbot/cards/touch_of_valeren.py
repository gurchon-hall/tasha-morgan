"""Touch of Valeren (Action/Combat). krcg 102262. Snapshot: data/cards/102262.json
Undirected, so "a minion" is one you control (Rulebook §8). The 1 blood is paid on
success for the action, at once in combat. [FOR]: another ready Salubri protects."""

from typing import Any

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire, discipline_level, has_discipline
from vtesbot.engine.allies import add_life
from vtesbot.engine.attachments import effective_capacity
from vtesbot.engine.damage import add_blood
from vtesbot.engine.hook_contexts import ActionCardPlayContext, DamagePreventionContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.phases.minion import ActionCardSpec, action_card_already_played_this_turn
from vtesbot.engine.state import AllyInPlay, GameState, VampireInPlay

KRCG_ID = 102262
NAME = "Touch of Valeren"
CLAN = "Salubri"
BLOOD_COST = 1
ACTION_STEALTH = 1
ADD_AMOUNT = 3
COMBAT_CARD_TYPE = "Combat"
VAMPIRE_IN_PLAY_ZONES = ("ready", "torpor")
ALLY_IN_PLAY_ZONES = ("ready",)

card = Card(KRCG_ID, NAME, "Action")


def _prevent_all(damage_box: dict[str, int]) -> None:
    """This strike only, unlike Rolling with the Punches [FOR]."""
    damage_box["normal"] = 0
    damage_box["aggravated"] = 0


def _has_damage(damage_box: dict[str, int]) -> bool:
    """[LSJ 20001114]: not usable without damage to prevent."""
    return damage_box.get("normal", 0) > 0 or damage_box.get("aggravated", 0) > 0


def _vampire_option(player: str, acting: VampireInPlay, target: VampireInPlay) -> HookOption:
    def _apply(s: GameState) -> ActionCardSpec:
        card.remove_from_hand(s, player)

        def resolve(_pending: dict[str, Any]) -> None:
            acting.blood -= BLOOD_COST
            add_blood(s, target, ADD_AMOUNT)

        return ActionCardSpec(
            base_stealth=ACTION_STEALTH, directed=False, resolve=resolve, name=NAME
        )

    return card.option(
        f"touch_of_valeren:action:blood:{target.instance_id}",
        f"Touch of Valeren [for]: add 3 blood to {target.card.name}",
        _apply,
    )


def _ally_option(player: str, acting: VampireInPlay, ally: AllyInPlay) -> HookOption:
    def _apply(s: GameState) -> ActionCardSpec:
        card.remove_from_hand(s, player)

        def resolve(_pending: dict[str, Any]) -> None:
            acting.blood -= BLOOD_COST
            add_life(ally, ADD_AMOUNT)

        return ActionCardSpec(
            base_stealth=ACTION_STEALTH, directed=False, resolve=resolve, name=NAME
        )

    return card.option(
        f"touch_of_valeren:action:life:{ally.instance_id}",
        f"Touch of Valeren [for]: add 3 life to {ally.name}",
        _apply,
    )


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_touch_of_valeren_action(
    state: GameState, ctx: ActionCardPlayContext
) -> list[HookOption]:
    player, acting = ctx["player"], context_vampire(state, ctx)
    if acting is None or acting.card.clan != CLAN or not has_discipline(state, acting, "for"):
        return []
    if not card.in_hand(state, player) or acting.blood < BLOOD_COST:
        return []
    if action_card_already_played_this_turn(state, acting, NAME):
        return []
    player_state = state.players[player]
    options = [
        _vampire_option(player, acting, v)
        for v in player_state.vampires.values()
        if v.zone in VAMPIRE_IN_PLAY_ZONES and effective_capacity(state, v) - v.blood > 0
    ]
    options += [
        _ally_option(player, acting, a)
        for a in player_state.allies.values()
        if a.zone in ALLY_IN_PLAY_ZONES and a.starting_life - a.life > 0
    ]
    return options


@card.on(Hook.DAMAGE_PREVENTION)
def _provide_touch_of_valeren_self(
    state: GameState, ctx: DamagePreventionContext
) -> list[HookOption]:
    """Combat strike damage only (`combat_state` set), as for Opikun."""
    player, damage_box = ctx["player"], ctx["damage"]
    if ctx["combat_state"] is None or not _has_damage(damage_box):
        return []
    vampire = context_vampire(state, ctx)
    if vampire is None or vampire.card.clan != CLAN or not has_discipline(state, vampire, "for"):
        return []
    if not card.in_hand(state, player) or vampire.blood < BLOOD_COST:
        return []

    def _apply(s: GameState) -> None:
        card.play_from_hand(s, player)
        vampire.blood -= BLOOD_COST
        _prevent_all(damage_box)

    return [
        card.option(
            "touch_of_valeren:combat:self",
            f"Touch of Valeren [for]: prevent all damage to {vampire.card.name} "
            "from the opposing minion's strike",
            _apply,
            played_card_type=COMBAT_CARD_TYPE,
        )
    ]


@card.on(Hook.DAMAGE_PREVENTION)
def _provide_touch_of_valeren_assist(
    state: GameState, ctx: DamagePreventionContext
) -> list[HookOption]:
    """Combat is one vampire a side, so any other ready vampire of the
    damaged one's controller is "not involved"; it pays the cost."""
    player, damage_box = ctx["player"], ctx["damage"]
    if ctx["combat_state"] is None or not _has_damage(damage_box):
        return []
    protected = context_vampire(state, ctx)
    if protected is None or not card.in_hand(state, player):
        return []
    options: list[HookOption] = []
    for candidate in state.players[player].vampires.values():
        if candidate.instance_id == protected.instance_id or candidate.zone != "ready":
            continue
        if candidate.card.clan != CLAN or discipline_level(state, candidate, "for") < 2:
            continue
        if candidate.blood < BLOOD_COST:
            continue

        def _apply(s: GameState, candidate: VampireInPlay = candidate) -> None:
            card.play_from_hand(s, player)
            candidate.blood -= BLOOD_COST
            _prevent_all(damage_box)

        options.append(
            card.option(
                f"touch_of_valeren:combat:assist:{candidate.instance_id}",
                f"Touch of Valeren [FOR]: {candidate.card.name} prevents all damage to "
                f"{protected.card.name} from the opposing minion's strike",
                _apply,
                played_card_type=COMBAT_CARD_TYPE,
            )
        )
    return options
