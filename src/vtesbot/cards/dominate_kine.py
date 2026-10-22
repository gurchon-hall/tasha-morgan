"""Dominate Kine (Action). krcg id 100573.

Card text (verbatim, via `krcg.load()` + `msgspec.json.encode()` in the
project's `uv run` virtualenv (krcg 5.14), 2026-10-16, matching the raw
snapshot saved to `data/cards/100573.json`):
    "[dom] +1 stealth action. Ⓓ Bleed with +1 bleed.
    [DOM] Ⓓ Steal a location."

Rulings (via krcg; both apply only to the superior clause -- the first
carries `symbols == [{"text": "[DOM]", ...}]`, the second is untagged
(`symbols == []`) but scoped by its own `group: "Changes controller of
location"`):
    - "If used to steal an equipment representing a location, it can be
      placed on any minion controlled by the new controller." [RTR
      19960112] -- same wording already carried by `disputed_territory.py`
      (krcg 100557); no "equipment representing a location" card is on the
      active 2P list (that module's own sweep, re-checked here), so the
      re-host branch (`engine/attachments.py::transfer_attachment_control`)
      stays unexercised here too.
    - "Changing the controller of a location has no other effect, unless
      specified by card text. Exception: a location 'on' another
      controlled card is moved onto an appropriate card controlled by the
      new controller." [RTR 19980623] -- satisfied for free by
      `transfer_master_card_control`, which does nothing beyond re-keying
      controller (no standalone location is ever "on" anything).

Card type: Action (`types == ["Action"]`). `discipline_requirement ==
{"type": "Mono", "disciplines": ["dom"]}`; `clan_requirement == []`;
`cost == {"type": "Blood", "value": 2}` (burned by the acting vampire,
only on the unblocked branch -- Rulebook §4 step 3, "If blocked -> action
card burned, cost not paid", mirrors `fleetness.py`'s own `BLOOD_COST`
convention). `burn_option is False`, `trifle is False`. Legal since
1994-09-15; on the active 2P allowed list (`data/formats/2p/
2026-10-03.json`).

Prey/predator check (`implement-card` skill step 3): both clauses carry
"Ⓓ" (Rulebook glossary "Directed Action"), collapsing to the single 2P
opponent (CLAUDE.md §3), same reading already used by `enchant_kindred.py`/
`fleetness.py`. Not RUL-001.

"+1 stealth action." (basic clause only): printed on the same line as
"[dom]", unlike `fleetness.py`'s shared pre-bracket baseline -- so
`base_stealth=1` applies only to the basic clause's bleed, not to the
superior clause's steal (which carries no stealth baseline of its own,
`base_stealth=0`). Bleed amount is the default (1) + this card's own
printed "+1 bleed" = 2, mirroring `enchant_kindred.py`'s
`BASIC_BLEED_BASE_AMOUNT` convention (composable with any other
bleed-amount hook, since `ActionCardSpec.action=ACTION_BLEED` is set, ENG-011
follow-up requirement).

"Ⓓ Steal a location." (superior clause): reuses `disputed_territory.py`'s
own `LOCATION_KRCG_IDS` sweep and `engine/master_cards.py::
transfer_master_card_control` -- the directed target is always the single
2P opponent, so eligible locations are exactly the opponent's own
`zone == "in_play"` `LOCATION_KRCG_IDS` cards; none offered (not "steal a
location that cannot resolve") if the opponent controls none. Target is
bound at announce time (`apply()`), not deferred to `resolve()` -- RUL-007
"all terms fixed at announce, re-validated at resolve" convention, same as
`enchant_kindred.py`'s target decision; `resolve()` treats a target that
left `zone == "in_play"` under the opponent's control between announce and
resolve as a fizzle (no effect).

ENG-037: both clauses call `remove_from_hand`
(not `play_from_hand`) and set `ActionCardSpec.name=NAME`, so `engine/
phases/minion.py::_perform_action_card` can interleave a future Reflex
card's own cancel-as-played window before drawing the replacement
(Finding 1), and so a second physical copy is not offered once either
clause has already been played this turn (Finding 2, keyed by `NAME` --
both clauses are the same physical card).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import remove_from_hand
from vtesbot.cards.disputed_territory import LOCATION_KRCG_IDS
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import ACTION_BLEED
from vtesbot.engine.attachments import effective_disciplines
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.master_cards import transfer_master_card_control
from vtesbot.engine.phases.minion import (
    ACTION_CARD_PLAY_HOOK,
    BLEED_AMOUNT_FIXED_MODIFIER_HOOK,
    BLEED_AMOUNT_MODIFIER_HOOK,
    PENDING_BLEED_AMOUNT_KEY,
    ActionCardSpec,
    action_card_already_played_this_turn,
)
from vtesbot.engine.pool import lose_pool
from vtesbot.engine.state import GameState, MasterCardInPlay, VampireInPlay

KRCG_ID = 100573
NAME = "Dominate Kine"
"""`ActionCardSpec.name`/`CardRegistration.name` (ENG-037): the generic "same
named action card at most once per turn" cap is keyed by this exact string for
both clauses -- they are the same physical card."""
BASIC = "dom"
SUPERIOR = "DOM"
BASIC_STEALTH = 1
"""Printed "+1 stealth action." -- on the `[dom]` line itself (module
docstring), so it applies only to the basic clause."""
BASIC_BLEED_BASE_AMOUNT = 2
"""Default bleed amount (1) + this card's own printed "+1 bleed", baked into
the baseline the same way `enchant_kindred.py`'s own constant is."""
BLOOD_COST = 2
"""Printed blood-cost box: burned from the acting vampire, only on the
unblocked branch, independent of which clause is used (module docstring)."""
CARD_TYPE = "Action"
"""`HookOption.played_card_type` (ENG-023): matches
this module's own "Card type: Action" docstring fact above."""


def _controllers_vampire(state: GameState, context: Mapping[str, Any]) -> VampireInPlay | None:
    return state.players[context["player"]].vampires.get(context["vampire"])


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _opponent_in_play_locations(state: GameState, opponent: str) -> list[MasterCardInPlay]:
    """The opponent's own `LOCATION_KRCG_IDS` cards currently `zone ==
    "in_play"` (module docstring's "Ⓓ Steal a location" paragraph) -- the
    directed target is always the single 2P opponent, so only their
    locations are ever eligible."""
    return [
        card
        for card in state.players[opponent].master_cards.values()
        if card.krcg_id in LOCATION_KRCG_IDS and card.zone == "in_play"
    ]


def _provide_dominate_kine_basic(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[dom] +1 stealth action. Ⓓ Bleed with +1 bleed." """
    player = context["player"]
    acting_vampire = _controllers_vampire(state, context)
    if acting_vampire is None:
        return []
    disciplines = effective_disciplines(state, acting_vampire)
    if BASIC not in disciplines and SUPERIOR not in disciplines:
        return []
    if not _has_card_in_hand(state, player):
        return []
    if acting_vampire.blood < BLOOD_COST:
        return []  # printed blood cost: must have enough blood to play at all.
    if action_card_already_played_this_turn(state, acting_vampire, NAME):
        return []  # ENG-037 Finding 2: same named action card, once per turn.

    def _apply(s: GameState) -> ActionCardSpec:
        remove_from_hand(s, player, KRCG_ID)

        def resolve(pending: dict[str, Any]) -> None:
            other = s.other_player(player)
            acting_vampire.blood -= BLOOD_COST  # paid now: action resolved unblocked.
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
            base_stealth=BASIC_STEALTH,
            directed=True,
            resolve=resolve,
            action=ACTION_BLEED,
            name=NAME,
        )

    return [
        HookOption(
            choice=Choice(
                "dominate_kine:basic", "Dominate Kine [dom]: +1 stealth action. Bleed with +1 bleed"
            ),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


def _provide_dominate_kine_superior(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "[DOM] Ⓓ Steal a location." """
    player = context["player"]
    acting_vampire = _controllers_vampire(state, context)
    if acting_vampire is None:
        return []
    if SUPERIOR not in effective_disciplines(state, acting_vampire):
        return []
    if not _has_card_in_hand(state, player):
        return []
    if acting_vampire.blood < BLOOD_COST:
        return []  # printed blood cost: must have enough blood to play at all.
    opponent = state.other_player(player)
    if not _opponent_in_play_locations(state, opponent):
        return []  # no legal target: do not offer a card play that cannot resolve.
    if action_card_already_played_this_turn(state, acting_vampire, NAME):
        return []  # ENG-037 Finding 2: same named action card, once per turn.

    def _apply(s: GameState) -> ActionCardSpec:
        remove_from_hand(s, player, KRCG_ID)

        # Target fixed at announce time, not deferred to resolve() -- RUL-007,
        # see module docstring.
        locations = _opponent_in_play_locations(s, opponent)
        if len(locations) == 1:
            target_id = locations[0].instance_id
        else:
            choices = tuple(
                Choice(f"dominate_kine_target:{card.instance_id}", f"Steal {card.name}")
                for card in locations
            )
            decision = Decision(player=player, kind="dominate_kine_target", choices=choices)
            chosen_value = s.ask(decision).value
            target_id = chosen_value.split(":", 1)[1]

        def resolve(pending: dict[str, Any]) -> None:
            del pending  # no later hook window of its own to feed.
            acting_vampire.blood -= BLOOD_COST  # paid now: action resolved unblocked.
            location = s.players[opponent].master_cards.get(target_id)
            if (
                location is None
                or location.controller != opponent
                or location.zone != "in_play"
                or location.krcg_id not in LOCATION_KRCG_IDS
            ):
                return  # fizzles (RUL-007 convention): no longer a legal target.
            transfer_master_card_control(s, location, player)

        return ActionCardSpec(
            base_stealth=0,
            directed=True,
            resolve=resolve,
            name=NAME,
        )

    return [
        HookOption(
            choice=Choice("dominate_kine:superior", "Dominate Kine [DOM]: steal a location"),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


hooks.register(ACTION_CARD_PLAY_HOOK, _provide_dominate_kine_basic)
hooks.register(ACTION_CARD_PLAY_HOOK, _provide_dominate_kine_superior)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.ACTION_CARD_PLAY,),
        source=__name__,
    )
)
