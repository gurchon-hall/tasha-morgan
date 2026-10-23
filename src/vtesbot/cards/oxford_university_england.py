"""Oxford University, England (Master). krcg 101341. Snapshot: data/cards/101341.json
A unique location (ENG-015), playable while you control a ready Brujah (Rulebook
§2 Requirements); its votes can be gained until polling closes (ENG-051)."""

from vtesbot.cards.card import Card
from vtesbot.engine.hook_contexts import MasterPhasePlayContext, PollingStepContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.master_cards import (
    bring_master_card_into_play,
    detect_contest_on_bring_into_play,
)
from vtesbot.engine.politics import variable_pool_burn_vote_options
from vtesbot.engine.state import GameState, MasterCardInPlay

KRCG_ID = 101341
NAME = "Oxford University, England"
CLAN_REQUIREMENT = ("Brujah",)
VOTES_PER_POOL = 2

card = Card(KRCG_ID, NAME, "Master")


def _controls_a_ready_brujah(state: GameState, player: str) -> bool:
    return any(
        vampire.zone == "ready" and vampire.card.clan in CLAN_REQUIREMENT
        for vampire in state.players[player].vampires.values()
    )


@card.on(Hook.MASTER_PHASE_PLAY)
def _play(state: GameState, ctx: MasterPhasePlayContext) -> list[HookOption]:
    player = ctx["player"]
    if not card.in_hand(state, player) or not _controls_a_ready_brujah(state, player):
        return []

    def _apply(s: GameState) -> bool:
        card.play_from_hand(s, player)
        in_play = bring_master_card_into_play(s, player, krcg_id=KRCG_ID, name=NAME)
        detect_contest_on_bring_into_play(s, in_play)
        return False  # not a trifle

    return [card.option("oxford_university_england", f"Play {NAME}", _apply)]


def _own_unlocked_in_play_instances(state: GameState, player: str) -> list[MasterCardInPlay]:
    return [
        in_play
        for in_play in state.players[player].master_cards.values()
        if in_play.krcg_id == KRCG_ID and in_play.is_unlocked_in_play
    ]


@card.on(Hook.POLLING_STEP)
def _votes(state: GameState, ctx: PollingStepContext) -> list[HookOption]:
    """ "Lock this card and burn X pool ... to get +2X votes": a standing
    ability, not a card play (`played_card_type` stays `None`, ENG-023)."""
    player = ctx["player"]
    options: list[HookOption] = []
    for in_play in _own_unlocked_in_play_instances(state, player):

        def _lock(s: GameState, in_play: MasterCardInPlay = in_play) -> None:
            in_play.locked = True

        options.extend(
            variable_pool_burn_vote_options(
                state,
                player,
                source_id_prefix=f"oxford:{in_play.instance_id}",
                label=NAME,
                votes_per_pool=VOTES_PER_POOL,
                pending=ctx["pending"],
                on_burn=_lock,
            )
        )
    return options
