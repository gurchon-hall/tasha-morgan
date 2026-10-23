"""Spirit's Touch (Reaction). krcg 101850. Snapshot: data/cards/101850.json
[AUS] leaves a grant that only the successful blocker can claim, in the resulting
combat [LSJ 20010813] [LSJ 20010819-2]. See ENG-040."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import discipline_level, has_discipline
from vtesbot.engine.action import grant_block_time_combat_effect
from vtesbot.engine.combat import block_time_combat_grant_available, consume_block_time_combat_grant
from vtesbot.engine.hook_contexts import InterceptModifierContext, ManeuverContext, Pending
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101850
NAME = "Spirit's Touch"
INTERCEPT_BONUS = 1
GRANT_NAME = "spirits_touch_block_maneuver"
USED_BY_KEY = "spirits_touch_used_by"

card = Card(KRCG_ID, NAME, "Reaction")


@card.on(Hook.INTERCEPT_MODIFIER)
def _provide_spirits_touch_intercept(
    state: GameState, ctx: InterceptModifierContext
) -> list[HookOption]:
    player = ctx["player"]
    if not card.in_hand(state, player):
        return []
    pending: Pending | None = ctx["pending"]
    used_by: set[str] = set() if pending is None else pending.setdefault(USED_BY_KEY, set())
    eligible = [
        v
        for v in state.players[player].vampires.values()
        if v.is_ready_unlocked and v.instance_id not in used_by and has_discipline(state, v, "aus")
    ]
    options: list[HookOption] = []
    for vampire in eligible:

        def _apply_basic(s: GameState, v: VampireInPlay = vampire) -> int:
            card.play_from_hand(s, player)
            used_by.add(v.instance_id)
            return INTERCEPT_BONUS

        def _apply_superior(s: GameState, v: VampireInPlay = vampire) -> int:
            card.play_from_hand(s, player)
            used_by.add(v.instance_id)
            grant_block_time_combat_effect(pending, v.instance_id, GRANT_NAME)
            return INTERCEPT_BONUS

        options.append(
            card.option(
                f"spirits_touch:basic:{vampire.instance_id}",
                f"Spirit's Touch [aus]: +{INTERCEPT_BONUS} intercept ({vampire.card.name})",
                _apply_basic,
            )
        )
        if discipline_level(state, vampire, "aus") == 2:
            options.append(
                card.option(
                    f"spirits_touch:superior:{vampire.instance_id}",
                    f"Spirit's Touch [AUS]: +{INTERCEPT_BONUS} intercept, 1 optional "
                    f"maneuver in the resulting combat if they block ({vampire.card.name})",
                    _apply_superior,
                )
            )
    return options


@card.on(Hook.MANEUVER)
def _provide_spirits_touch_maneuver(state: GameState, ctx: ManeuverContext) -> list[HookOption]:
    if not block_time_combat_grant_available(ctx, GRANT_NAME):
        return []

    def _apply(_s: GameState) -> None:
        consume_block_time_combat_grant(ctx, GRANT_NAME)

    return [
        card.option(
            "spirits_touch:maneuver",
            "Spirit's Touch: optional maneuver",
            _apply,
            played_card_type=None,  # claims the grant; the card was played at the block
        )
    ]
