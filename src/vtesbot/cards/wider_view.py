"""Wider View (Master). krcg id 102180.

Card text (verbatim via `krcg.load()[102180].card_text`, re-confirmed live
2026-10-11, matching the raw snapshot saved to `data/cards/102180.json` per
the `implement-card` skill, and matching both active 2P suggested decklists'
own entries, `data/decks/vekn-2p/brujah.json` / `data/decks/vekn-2p/
toreador.json`):
    "Trifle.
    Put this card in play. You can use 1 transfer to draw 1 card from your
    crypt and then remove a crypt card in your uncontrolled region from the
    game. You can use 4 transfers to burn this card and gain 2 pool."

Ruling (verbatim, one on file): "Cards removed from the game are public.
[LSJ 20080314]".

Card type: Master (`types == ["Master"]`). `clan_requirement == []`,
`discipline_requirement.disciplines == []` (no clan/discipline needed).
`trifle is True`.

Correction to this task's own brief, found while re-verifying live rather
than trusting the paraphrase handed down (CLAUDE.md "no guessing" / "text
first"): the task description asserted `pool_cost=None`. Re-checked directly
against both the live `api.krcg.org/card/102180` endpoint and the installed
`krcg` package (`krcg.load()[102180].cost`) -- both report
`cost = Cost(type=Pool, value=1)`, i.e. this card costs 1 pool to play, not
free. Rulebook SS2 Card Types > "Requirements for Playing Cards" (quoted in
full in `oxford_university_england.py`'s own docstring; re-fetched here
too, matching the local cache `data/sources/rulebook/2026-10-09/
2-card-types.md`): "A number in a white diamond with a skull represents pool
cost (the amount of pool the Methuselah must burn). Only a Methuselah with
enough pool can play a card with a pool cost." So playing Wider View both
requires >= 1 pool and burns it as part of being played -- implemented below
via `lose_pool` in the master-phase-play `apply`, gated by `pool >= POOL_COST`
in the provider itself (legality by construction, same invariant every other
hook provider in this engine already follows).

Three independent clauses, matching `data/cards/102180.json`'s own `text`
field split at each sentence:

1. "Trifle.\nPut this card in play." -- identical shape to Oxford
   University, England (`src/vtesbot/cards/oxford_university_england.py`,
   OQ-23 `docs/OPEN_QUESTIONS.md`): registers a `"master_phase_play"`
   provider that pays the 1-pool cost above, then calls `play_from_hand`
   (`src/vtesbot/cards/_shared.py`) then `bring_master_card_into_play`
   (`src/vtesbot/engine/master_cards.py`). Unlike Oxford, this card is
   printed "Trifle." (not "Unique."), so: (a) `detect_contest_on_bring_
   into_play` is never called -- it is only ever correct for a card printed
   "Unique" (`engine/master_cards.py`'s own module/function docstrings,
   OQ-23), and this card's own text carries no such clause (confirmed by
   OQ-23's own 18-card sweep, which names Wider View by id as *the*
   non-unique counter-example motivating `MasterCardInPlay`'s generic,
   not-unique-scoped shape); (b) `apply(state)` returns `True` (Rulebook SS4
   Master Phase: "trifles grant one extra [master phase action]"), unlike
   Oxford's `False`. No clan/discipline gate beyond "card is in hand" and
   "enough pool", since this card prints neither.

2. "You can use 1 transfer to draw 1 card from your crypt and then remove a
   crypt card in your uncontrolled region from the game." -- registered
   against `INFLUENCE_PHASE_ACTION_HOOK` (`src/vtesbot/engine/phases/
   influence.py`, OQ-24 `docs/OPEN_QUESTIONS.md`). `HookOption.apply(state)`
   returns `1` (transfers consumed), per that hook's own documented
   contract.

   Sequencing ("draw... and then remove"), resolved directly from the
   Rulebook's own glossary rather than guessed (CLAUDE.md "no guessing" --
   this was checked, not picked): SS8 Glossary "Draw": "Crypt cards are
   drawn from the top of the Methuselah's crypt into their uncontrolled
   region." So "draw 1 card from your crypt" means exactly what the
   engine's own pre-existing `influence.py::_apply`'s `"bring_crypt"` branch
   already does -- `crypt_deck.pop(0)` into a new `VampireInPlay` with
   `zone="uncontrolled"` -- and that drawn card is, by the glossary's own
   wording, already "in your uncontrolled region" the instant the draw
   completes, *before* the "and then remove a crypt card in your
   uncontrolled region" clause is ever evaluated. The text does not say
   "another" or "a different" crypt card -- "a crypt card in your
   uncontrolled region" is therefore satisfied by the complete,
   post-draw set of the controller's own uncontrolled vampires, which
   necessarily includes the one just drawn. This is a direct textual/
   sourced reading, not an inference beyond the printed rule, so no Open
   Question is raised for it: the ability is legal whenever there is a
   crypt card left to draw at all (`crypt_deck` non-empty) -- no separate
   "needs a pre-existing uncontrolled vampire" gate exists, because the
   freshly-drawn card is itself always a legal (if sometimes pointless --
   look at the top of your crypt, then put it right back out of the game)
   removal target the moment the draw itself is legal. Implemented via
   `remove_vampire_from_game` (`src/vtesbot/engine/damage.py`) for the
   removal half; if, after the draw, more than one of the controller's own
   uncontrolled vampires exists, the controller is offered a sub-`Decision`
   choosing which one to remove (mirrors `src/vtesbot/cards/line_brawl.py`/
   `enchant_kindred.py`'s own per-target `Choice` pattern) -- never
   auto-picked.

   Offered only while: (a) the controller controls at least one of this
   card's own instances with `zone == "in_play"` (the ability is granted by
   having *a* copy in play -- this clause carries no "lock this card"
   wording at all, unlike Oxford's "you can lock this card and burn X
   pool...": re-read verbatim above, confirmed no locking mechanic is
   printed here, so none is modelled -- a burned/contested instance grants
   nothing, but an in-play one is never locked by using this ability,
   mirroring `MasterCardInPlay.locked`'s own documented default-`False`,
   never-set-by-this-clause behaviour); (b) `transfers_remaining >= 1`;
   (c) `state.players[player].crypt_deck` is non-empty (legality by
   construction, `GameState.ask`'s own invariant -- without this gate the
   draw itself would have nothing to draw).

3. "You can use 4 transfers to burn this card and gain 2 pool." --
   registered against the same `INFLUENCE_PHASE_ACTION_HOOK`, one option per
   own in-play instance (mirrors Oxford's own `_own_unlocked_in_play_
   instances` per-instance enumeration, since burning is a specific
   instance's own fate): `apply(state)` burns that instance (`zone =
   "burned"`) and calls `gain_pool(state, player, 2)`
   (`src/vtesbot/engine/pool.py`), returning `4`. Offered only while
   `transfers_remaining >= 4` and that instance is still `zone == "in_play"`
   (a `"burned"` copy cannot be burned again; a `"contested"` one is out of
   play and inert, same as clause 2's own in-play gate).

Choice-value namespacing (OQ-24 addendum, `hooks.ensure_unique_choice_
values`): every `Choice.value` here is prefixed `"wider_view_"`, matching
the convention every other card module already follows.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.damage import remove_vampire_from_game
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.master_cards import bring_master_card_into_play
from vtesbot.engine.phases.influence import INFLUENCE_PHASE_ACTION_HOOK
from vtesbot.engine.pool import gain_pool, lose_pool
from vtesbot.engine.state import GameState, MasterCardInPlay, VampireInPlay

KRCG_ID = 102180
NAME = "Wider View"
MASTER_PHASE_PLAY_HOOK = "master_phase_play"
POOL_COST = 1
BURN_TRANSFER_COST = 4
BURN_POOL_GAIN = 2


def _own_in_play_instances(state: GameState, player: str) -> list[MasterCardInPlay]:
    return [
        card
        for card in state.players[player].master_cards.values()
        if card.krcg_id == KRCG_ID and card.zone == "in_play"
    ]


# --- Clause 1: "Trifle. Put this card in play." -----------------------------


def _provide_wider_view_master_phase_play(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    player = context["player"]
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []
    if state.players[player].pool < POOL_COST:
        return []

    def _apply(s: GameState) -> bool:
        lose_pool(s, player, POOL_COST)
        play_from_hand(s, player, KRCG_ID)
        bring_master_card_into_play(s, player, krcg_id=KRCG_ID, name=NAME)
        return True  # Trifle: grants the one extra master phase action.

    return [
        HookOption(
            choice=Choice("wider_view_play", f"Play {NAME} (1 pool)"),
            apply=_apply,
        )
    ]


# --- Clause 2: "1 transfer: draw 1 card from your crypt and then remove a
# crypt card in your uncontrolled region from the game." --------------------


def _provide_wider_view_draw_and_remove(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    player = context["player"]
    if context["transfers_remaining"] < 1:
        return []
    if not _own_in_play_instances(state, player):
        return []
    p = state.players[player]
    if not p.crypt_deck:
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
            chosen_value = s.ask(decision).value
            target_id = chosen_value.split(":", 1)[1]
            target = p.vampires[target_id]
        remove_vampire_from_game(s, player, target)
        return 1

    return [
        HookOption(
            choice=Choice("wider_view_draw_and_remove", f"{NAME}: draw and remove (1 transfer)"),
            apply=_apply,
        )
    ]


# --- Clause 3: "4 transfers: burn this card and gain 2 pool." --------------


def _provide_wider_view_burn_for_pool(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    player = context["player"]
    if context["transfers_remaining"] < BURN_TRANSFER_COST:
        return []

    options: list[HookOption] = []
    for card in _own_in_play_instances(state, player):

        def _apply(s: GameState, card: MasterCardInPlay = card) -> int:
            card.zone = "burned"
            card.locked = False
            gain_pool(s, player, BURN_POOL_GAIN)
            return BURN_TRANSFER_COST

        options.append(
            HookOption(
                choice=Choice(
                    f"wider_view_burn_for_pool:{card.instance_id}",
                    f"Burn {NAME} for {BURN_POOL_GAIN} pool ({BURN_TRANSFER_COST} transfers)",
                ),
                apply=_apply,
            )
        )
    return options


hooks.register(MASTER_PHASE_PLAY_HOOK, _provide_wider_view_master_phase_play)
hooks.register(INFLUENCE_PHASE_ACTION_HOOK, _provide_wider_view_draw_and_remove)
hooks.register(INFLUENCE_PHASE_ACTION_HOOK, _provide_wider_view_burn_for_pool)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.MASTER_PHASE_PLAY, Hook.INFLUENCE_PHASE_ACTION),
        source=__name__,
    )
)
