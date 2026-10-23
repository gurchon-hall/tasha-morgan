"""Fame (Master). krcg 100698. Snapshot: data/cards/100698.json
Goes on a ready vampire of either player; a contested copy does nothing
(ENG-014)."""

from vtesbot.cards.card import Card
from vtesbot.engine.attachments import attach_card, detect_contest_on_attach, iter_attachments
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.hook_contexts import (
    MasterPhasePlayContext,
    UnlockPhaseMandatoryEffectContext,
    VampireEntersTorporContext,
)
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.pool import lose_pool
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 100698

card = Card(KRCG_ID, "Fame", "Master")


def _active_fame(vampire: VampireInPlay) -> CardAttachment | None:
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
        vampire
        for player_state in state.players.values()
        for vampire in player_state.vampires.values()
        if vampire.zone == "ready"
    ]
    options: list[HookOption] = []
    for vampire in targets:

        def _apply(s: GameState, vampire: VampireInPlay = vampire) -> bool:
            card.play_from_hand(s, player)
            # Rulebook §2 Master Cards: controlled by whoever played it.
            attachment = attach_card(s, vampire, controller=player, krcg_id=KRCG_ID, name="Fame")
            detect_contest_on_attach(s, attachment)
            return False  # not a trifle

        options.append(
            card.option(
                f"fame:{vampire.instance_id}",
                f"Fame: attach to {vampire.card.name} ({vampire.controller})",
                _apply,
            )
        )
    return options


@card.on(Hook.VAMPIRE_ENTERS_TORPOR)
def _torpor_burn(state: GameState, ctx: VampireEntersTorporContext) -> None:
    """ "Their controller burns 3 pool": the host vampire's controller, who
    need not control Fame."""
    vampire = ctx["vampire"]
    if _active_fame(vampire) is not None:
        lose_pool(state, vampire.controller, 3)


@card.on(Hook.UNLOCK_PHASE_MANDATORY_EFFECT)
def _unlock_burn(state: GameState, ctx: UnlockPhaseMandatoryEffectContext) -> list[HookOption]:
    """ "That Methuselah" is whoever's unlock phase it is. An option, not a
    direct burn: it "can be ordered with other unlock effects" [LSJ 20110121]."""
    player = ctx["player"]
    options: list[HookOption] = []
    for vampire, attachment in iter_attachments(state):
        if attachment.krcg_id == KRCG_ID and attachment.zone == "attached":
            if vampire.zone != "torpor":
                continue

            def _apply(s: GameState, player: str = player) -> None:
                lose_pool(s, player, 1)

            options.append(
                card.option(
                    f"fame_unlock_burn:{attachment.instance_id}",
                    f"Fame: burn 1 pool ({vampire.card.name} in torpor)",
                    _apply,
                    played_card_type=None,
                )
            )
    return options
