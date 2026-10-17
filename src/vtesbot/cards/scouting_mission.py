"""Scouting Mission (Action). krcg id 101698.

Card text (verbatim, re-verified via the installed `krcg` package's own raw
snapshot and cross-checked live against `https://api.krcg.org/card/101698`,
2026-10-17; both match `data/cards/101698.json` byte-for-byte):
    "[dom] Ⓓ Bleed with +1 bleed.
    [DOM] +1 stealth action. Add 2 blood to a younger vampire in your
    uncontrolled region."

Rulings: none on file -- `rulings == []`, both via the installed `krcg`
package and the live API (re-checked 2026-10-17).

Card type: Action (`types == ["Action"]`, *not* "Action Modifier").
`discipline_requirement == {"type": "Mono", "disciplines": ["dom"]}` (basic
Dominate required to play the card at all; superior Dominate, printed
uppercase "DOM" on a `CryptCard`, additionally unlocks the second clause --
Rulebook §3 "Discipline symbol within a diamond ... may opt to use either
the basic (plain text) or the superior (bold) effect ... but not both").
`clan_requirement == []`, `cost is None`, `burn_option is False`,
`trifle is False`.

Status: implemented. Textually identical to the already-implemented
"Enchant Kindred" (krcg id 100640, `enchant_kindred.py`) except for the
discipline (Dominate instead of Presence) -- same `ACTION_CARD_PLAY_HOOK`
shape, same two OQs it rides on: OQ-17 (`docs/open_questions_archive/
002.md`, generic "Action"-typed library card self-contained minion action
entry point: `engine/phases/minion.py::ACTION_CARD_PLAY_HOOK` /
`ActionCardSpec` / `_perform_action_card`) and OQ-57
(`docs/OPEN_QUESTIONS.md`, both clauses `remove_from_hand` + shared
`ActionCardSpec.name=NAME` so a second physical copy is not offered once
either clause has been played this turn). The basic clause's bleed is
tagged `action=ACTION_BLEED` for the same reason as Enchant Kindred's (an
existing bleed-gated provider sharing the block-attempt/bleed-amount window,
e.g. Bonding's superior clause, must still fire).

"a younger vampire" (superior clause): per OQ-17's own resolution, confirmed
by the project owner and already applied to Enchant Kindred's identical
wording -- strictly lower *printed* capacity (`vampire.card.capacity`) than
the acting vampire, not `effective_capacity` (used here, as there, only for
the destination's own blood-capacity room check, per OQ-8). OQ-21
(`docs/open_questions_archive/002.md`): the target is chosen at `apply()`
time (announce), `resolve()` only re-validates it, never re-chooses --
fizzles if no longer eligible. Target region "in your uncontrolled region":
own uncontrolled region only, and not already at (effective) capacity.

Both clauses collapse to the engine's existing single-opponent block-attempt
model for a 2P duel (`engine/action.py`'s own module docstring), so neither
raises a fresh prey/predator question.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import remove_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import effective_capacity, hooks
from vtesbot.engine.action import ACTION_BLEED
from vtesbot.engine.damage import add_blood
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import (
    ACTION_CARD_PLAY_HOOK,
    BLEED_AMOUNT_FIXED_MODIFIER_HOOK,
    BLEED_AMOUNT_MODIFIER_HOOK,
    PENDING_BLEED_AMOUNT_KEY,
    ActionCardSpec,
    action_card_already_played_this_turn,
)
from vtesbot.engine.pool import lose_pool
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101698
NAME = "Scouting Mission"
"""`ActionCardSpec.name`/`CardRegistration.name` (OQ-57, `docs/
OPEN_QUESTIONS.md`): the generic "same named action card at most once per
turn" cap is keyed by this exact string for both clauses -- they are the
same physical card."""
BASIC = "dom"
SUPERIOR = "DOM"
BASIC_BLEED_BASE_AMOUNT = 2
"""Default bleed amount (1) + this card's own printed "+1 bleed", baked into
the baseline the same way `_perform_bleed`'s own `BLEED_AMOUNT` constant (1)
is -- not a separately-offered, declinable modifier."""
SUPERIOR_STEALTH = 1
"""This card's own printed "+1 stealth" baseline for its undirected action
(mirrors `HUNT_STEALTH`/`RECRUIT_ALLY_STEALTH`, `engine/phases/minion.py`),
not a modifier layered on top of a 0 baseline."""
ADD_BLOOD_AMOUNT = 2
CARD_TYPE = "Action"
"""`HookOption.played_card_type` (OQ-33, `docs/open_questions_archive/
002.md`): matches this module's own "Card type: Action" docstring fact
above."""


def _eligible_targets(
    state: GameState, player: str, acting_vampire: VampireInPlay
) -> list[VampireInPlay]:
    player_state = state.players[player]
    return [
        v
        for v in player_state.vampires.values()
        if v.zone == "uncontrolled"
        and v.card.capacity < acting_vampire.card.capacity
        and effective_capacity(state, v) - v.blood > 0
    ]


def _provide_scouting_mission_basic(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "[dom] Ⓓ Bleed with +1 bleed" -- a directed bleed, amount 2."""
    player = context["player"]
    acting_vampire_id = context["vampire"]
    acting_vampire = state.players[player].vampires.get(acting_vampire_id)
    if acting_vampire is None:
        return []  # `player` is the defender this window, not the acting player.

    disciplines = acting_vampire.card.disciplines
    if BASIC not in disciplines and SUPERIOR not in disciplines:
        return []
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []
    if action_card_already_played_this_turn(state, acting_vampire, NAME):
        return []  # OQ-57 Finding 2: same named action card, once per turn.

    def _apply(s: GameState) -> ActionCardSpec:
        remove_from_hand(s, player, KRCG_ID)

        def resolve(pending: dict[str, Any]) -> None:
            other = s.other_player(player)
            base_amount = (
                BASIC_BLEED_BASE_AMOUNT
                + hooks.sum_modifiers(
                    BLEED_AMOUNT_FIXED_MODIFIER_HOOK,
                    s,
                    player=player,
                    vampire=acting_vampire.instance_id,
                )
                + pending.get(PENDING_BLEED_AMOUNT_KEY, 0)
            )
            amount_box = [base_amount]
            hooks.resolve_impulse_window(
                s,
                BLEED_AMOUNT_MODIFIER_HOOK,
                player,
                other,
                context={
                    "vampire": acting_vampire.instance_id,
                    "amount": amount_box,
                    "pending": pending,
                },
            )
            amount = max(0, amount_box[0])
            lose_pool(s, other, amount)
            if amount >= 1:
                s.edge_holder = player

        return ActionCardSpec(
            base_stealth=0,
            directed=True,
            resolve=resolve,
            action=ACTION_BLEED,
            name=NAME,
        )

    return [
        HookOption(
            choice=Choice("scouting_mission:basic", "Scouting Mission [dom]: Bleed with +1 bleed"),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


def _provide_scouting_mission_superior(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "[DOM] +1 stealth action. Add 2 blood to a younger vampire in your
    uncontrolled region." -- an undirected action."""
    player = context["player"]
    acting_vampire_id = context["vampire"]
    acting_vampire = state.players[player].vampires.get(acting_vampire_id)
    if acting_vampire is None:
        return []

    if SUPERIOR not in acting_vampire.card.disciplines:
        return []
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []
    if not _eligible_targets(state, player, acting_vampire):
        return []  # no legal target: do not offer a card play that cannot resolve.
    if action_card_already_played_this_turn(state, acting_vampire, NAME):
        return []  # OQ-57 Finding 2: same named action card, once per turn.

    def _apply(s: GameState) -> ActionCardSpec:
        remove_from_hand(s, player, KRCG_ID)

        # Target fixed at announce time, not deferred to resolve() -- OQ-21,
        # see module docstring.
        targets = _eligible_targets(s, player, acting_vampire)
        if len(targets) == 1:
            target_id = targets[0].instance_id
        else:
            choices = tuple(
                Choice(
                    f"scouting_mission_target:{v.instance_id}",
                    f"Add 2 blood to {v.card.name}",
                )
                for v in targets
            )
            decision = Decision(player=player, kind="scouting_mission_target", choices=choices)
            chosen_value = s.ask(decision).value
            target_id = chosen_value.split(":", 1)[1]

        def resolve(pending: dict[str, Any]) -> None:
            del pending  # no later window of its own to feed.
            target = s.players[player].vampires.get(target_id)
            if target is None or target not in _eligible_targets(s, player, acting_vampire):
                return  # fizzles (OQ-21); not reachable today, but correct either way.
            add_blood(s, target, ADD_BLOOD_AMOUNT)

        return ActionCardSpec(
            base_stealth=SUPERIOR_STEALTH,
            directed=False,
            resolve=resolve,
            name=NAME,
        )

    return [
        HookOption(
            choice=Choice(
                "scouting_mission:superior",
                "Scouting Mission [DOM]: +1 stealth action. "
                "Add 2 blood to a younger vampire in your uncontrolled region",
            ),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


hooks.register(ACTION_CARD_PLAY_HOOK, _provide_scouting_mission_basic)
hooks.register(ACTION_CARD_PLAY_HOOK, _provide_scouting_mission_superior)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.ACTION_CARD_PLAY,),
        source=__name__,
    )
)
