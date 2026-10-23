"""Perfectionist (Master). krcg 101388. Snapshot: data/cards/101388.json
"Successful" means unblocked, whatever a referendum then does (Rulebook §4). A
vampire you control in play, torpid included, without a Perfectionist."""

from vtesbot.cards.card import Card
from vtesbot.engine import hooks
from vtesbot.engine.attachments import attach_card
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.damage import add_blood
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hook_contexts import ActionSucceededContext, MasterPhasePlayContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101388
ABILITY_USED_KEY = "perfectionist_gain_blood"
IN_PLAY_ZONES = ("ready", "torpor")

card = Card(KRCG_ID, "Perfectionist", "Master")


def _active_perfectionist(vampire: VampireInPlay) -> CardAttachment | None:
    for attachment in vampire.attachments:
        if attachment.krcg_id == KRCG_ID and attachment.zone == "attached":
            return attachment
    return None


@card.on(Hook.MASTER_PHASE_PLAY)
def _play(state: GameState, ctx: MasterPhasePlayContext) -> list[HookOption]:
    player = ctx["player"]
    if not card.in_hand(state, player):
        return []
    targets = [
        v
        for v in state.players[player].vampires.values()
        if v.zone in IN_PLAY_ZONES and _active_perfectionist(v) is None
    ]
    options: list[HookOption] = []
    for vampire in targets:

        def _apply(s: GameState, vampire: VampireInPlay = vampire) -> bool:
            card.play_from_hand(s, player)
            attach_card(s, vampire, controller=player, krcg_id=KRCG_ID, name="Perfectionist")
            return False  # not a trifle

        options.append(
            card.option(
                f"perfectionist:{vampire.instance_id}",
                f"Perfectionist: attach to {vampire.card.name}",
                _apply,
            )
        )
    return options


@card.on(Hook.ACTION_SUCCEEDED)
def _gain_blood(state: GameState, ctx: ActionSucceededContext) -> None:
    """Once in each player's turn [ANK 20180719-4], the controller may gain 1
    blood [ANK 20210309-3], unless a reaction was played, even one cancelled
    as played [LSJ 20070330]."""
    vampire = ctx["vampire"]
    if _active_perfectionist(vampire) is None:
        return
    if vampire.ability_used_turn.get(ABILITY_USED_KEY) == state.turn_number:
        return
    if ctx["pending"].get(hooks.PENDING_REACTION_PLAYED_KEY, False):
        return
    decision = Decision(
        player=vampire.controller,
        kind="perfectionist_gain_blood",
        choices=(
            Choice("gain", "Perfectionist: gain 1 blood"),
            Choice("decline", "Decline"),
        ),
        context=hooks.sanitize_decision_context({"vampire": vampire.instance_id}),
    )
    if state.ask(decision).value == "gain":
        vampire.ability_used_turn[ABILITY_USED_KEY] = state.turn_number
        add_blood(state, vampire, 1)
