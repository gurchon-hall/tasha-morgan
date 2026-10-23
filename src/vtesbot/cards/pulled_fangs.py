"""Pulled Fangs (Combat). krcg 101515. Snapshot: data/cards/101515.json
"Only one Pulled Fangs" caps the host, the opposing vampire. Its player keeps
control of it; any vampire may act to burn it [ANK 20170202-2]."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire, window_sides
from vtesbot.engine.attachments import attach_card, iter_attachments
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.combat import CLOSE_RANGE
from vtesbot.engine.damage import apply_damage, damage_successfully_inflicted_this_round
from vtesbot.engine.hook_contexts import (
    AttachmentRemovalActionPlayContext,
    CannotHuntContext,
    EndOfRoundContext,
)
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.phases.minion import ActionCardSpec, build_attachment_removal_action_spec
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101515
NAME = "Pulled Fangs"
DAMAGE_AMOUNT = 1
CONTRIBUTIONS_REQUIRED = 2
_EXCLUDED_ZONES = ("burned", "torpor")

card = Card(KRCG_ID, NAME, "Combat")


def _has_attached_pulled_fangs(vampire: VampireInPlay) -> bool:
    return any(a.krcg_id == KRCG_ID and a.zone == "attached" for a in vampire.attachments)


@card.on(Hook.END_OF_ROUND)
def _play(state: GameState, ctx: EndOfRoundContext) -> list[HookOption]:
    """Only the playing vampire's zone is checked, as for Taste of Vitae."""
    player, round_state = ctx["player"], ctx["round_state"]
    vampire_id, opponent_player, opponent_id = window_sides(ctx)
    vampire = state.players[player].vampires.get(vampire_id)
    opponent = state.players[opponent_player].vampires.get(opponent_id)
    if vampire is None or opponent is None or vampire.zone in _EXCLUDED_ZONES:
        return []
    if not card.in_hand(state, player) or state.combat_range != CLOSE_RANGE:
        return []
    if _has_attached_pulled_fangs(opponent):
        return []
    inflicted = damage_successfully_inflicted_this_round(round_state, vampire_id)
    if inflicted <= damage_successfully_inflicted_this_round(round_state, opponent_id):
        return []

    def _apply(s: GameState) -> None:
        card.play_from_hand(s, player)
        live_opponent = s.players[opponent_player].vampires.get(opponent_id)
        if live_opponent is None:
            return  # fizzles (RUL-007): the opposing vampire left play since the offer
        attach_card(s, live_opponent, controller=player, krcg_id=KRCG_ID, name=NAME)
        apply_damage(
            s,
            opponent_player,
            live_opponent,
            normal=DAMAGE_AMOUNT,
            round_state=round_state,
            inflicted_by=vampire_id,
        )

    return [
        card.option(
            "pulled_fangs",
            f"Pulled Fangs: attach to {opponent.card.name}, inflict {DAMAGE_AMOUNT} damage",
            _apply,
        )
    ]


@card.on(Hook.CANNOT_HUNT)
def _cannot_hunt(state: GameState, ctx: CannotHuntContext) -> bool:
    vampire = context_vampire(state, ctx)
    return vampire is not None and _has_attached_pulled_fangs(vampire)


def _live_attachments(state: GameState) -> list[tuple[VampireInPlay, CardAttachment]]:
    return [
        (host, attachment)
        for host, attachment in iter_attachments(state)
        if attachment.krcg_id == KRCG_ID and attachment.zone == "attached"
    ]


@card.on(Hook.ATTACHMENT_REMOVAL_ACTION_PLAY)
def _burn_action(state: GameState, ctx: AttachmentRemovalActionPlayContext) -> list[HookOption]:
    """Offered to every acting vampire, whoever controls it or the host."""
    del ctx
    options: list[HookOption] = []
    for host, attachment in _live_attachments(state):

        def _apply(_s: GameState, attachment: CardAttachment = attachment) -> ActionCardSpec:
            return build_attachment_removal_action_spec(
                attachment, contributions_required=CONTRIBUTIONS_REQUIRED
            )

        options.append(
            card.option(
                f"pulled_fangs:remove:{attachment.instance_id}",
                f"Pulled Fangs: contribute to burning (attached to {host.card.name})",
                _apply,
                played_card_type=None,  # an action, not a card play
            )
        )
    return options
