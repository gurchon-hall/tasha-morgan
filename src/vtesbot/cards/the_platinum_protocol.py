"""The Platinum Protocol (Action). krcg id 102232.

Card text (verbatim, via the project's `uv run` venv (krcg 5.14), fetched
2026-10-18, matching the raw snapshot `data/cards/102232.json` byte-for-byte):
    "Requires an Anarch. More than one Discipline can be used to play this
    card. Ⓓ Bleed.
    [obf] This is a +1 stealth action.
    [pre] The bleed is with +1 bleed.
    [pro] Put 1 corruption counter on a minion controlled by the target
    Methuselah if the bleed is successful (for 1 or more)."

Rulings (verbatim, via krcg, `data/cards/102232.json`):
    - "[pro] The minion getting the corruption counter is chosen at action
      resolution (not declaration)." [ANK 20240706] [LSJ 20080608]
    - "[pro] Putting a corruption counter on a minion does not give you an
      opportunity to steal it." [ANK 20200925] [ANK 20211105]
    - "When played, a multi-Disciplines card counts as requiring the
      Discipline(s) being used. In the hand, library, or ash heap, the card
      is considered to require any and/or all Disciplines listed on it."
      [LSJ 20011204-3] [PIB 20130704]

Card type: Action (`types == ["Action"]`). `discipline_requirement ==
{"type": "Choice", "disciplines": ["obf", "pre", "pro"]}` -- at least one of
the three (basic level; no uppercase/superior variant printed) is needed to
play the card at all. `clan_requirement == []`, `cost is None`. Legal since
2021-12-31; confirmed on the active 2P allowed list (`data/formats/2p/
2026-10-03.json`) and in the suggested 2P decklist `data/decks/vekn-2p/
ministry.json` (4 copies).

Status: implemented.

Unlike Line Brawl/Dust Up (also `Choice`-typed "Requires an Anarch" cards),
only the unbracketed sentence carries "Ⓓ Bleed"; each bracket is a fragment
modifying *that* one bleed, and this is the only one of the three printing
"More than one Discipline can be used to play this card." Rulebook §2 Card
Types > Requirements for Playing Cards (`data/sources/rulebook/2026-10-09/
2-card-types.md:150-153`): "...some effects may require the vampire to
possess several Disciplines" -- so every bracket whose discipline the
vampire possesses applies simultaneously on the base bleed, not a choice of
one; no decline is offered per bracket (each is a flat bonus, no "may").

"[obf]"/"[pre]": `base_stealth`/bleed amount from which disciplines are
held, composed via the same `BLEED_AMOUNT_FIXED_MODIFIER_HOOK`/
`BLEED_AMOUNT_MODIFIER_HOOK`/`PENDING_BLEED_AMOUNT_KEY` chain as
`enchant_kindred.py`/`line_brawl.py`, `action=ACTION_BLEED` likewise (ENG-011).

"[pro]": gated on `amount >= 1` ("(for 1 or more)"), same threshold
`enchant_kindred.py`/`line_brawl.py` use for their own Edge-holder check.
Target pool is the defender's own `"ready"`/`"torpor"` vampires only --
`corruption_counters` lives on `VampireInPlay` only (`engine/corruption.py`'s
own docstring; no legal-2P card places it on an ally), and torpor still
counts as "controlled" (Sergio Bueno's own on-file ruling that an identical
keyword "applies even if the vampire is in torpor"). Chosen at *resolution*,
not declaration (first ruling above) -- raised inside `resolve()`, after
`lose_pool`, contrary to every other RUL-007 "bind at announce" case in this
pool, since this card's own ruling explicitly overrides that default.
Chosen by this card's own controller (mirrors `aniel.py`'s identical
convention); fizzles with no counter placed if no eligible target exists at
resolution, or `amount` never reached 1 (RUL-007 fizzle convention).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import remove_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import ACTION_BLEED
from vtesbot.engine.attachments import effective_disciplines
from vtesbot.engine.cards import Sect
from vtesbot.engine.corruption import add_corruption_counters
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import (
    ACTION_CARD_PLAY_HOOK,
    BLEED_AMOUNT,
    BLEED_AMOUNT_FIXED_MODIFIER_HOOK,
    BLEED_AMOUNT_MODIFIER_HOOK,
    PENDING_BLEED_AMOUNT_KEY,
    ActionCardSpec,
    action_card_already_played_this_turn,
)
from vtesbot.engine.pool import lose_pool
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 102232
NAME = "The Platinum Protocol"
OBF = "obf"
PRE = "pre"
PRO = "pro"
STEALTH_BONUS = 1
"""Printed "[obf] This is a +1 stealth action."."""
PRE_BLEED_BONUS = 1
"""Printed "[pre] The bleed is with +1 bleed."."""
CARD_TYPE = "Action"
"""`HookOption.played_card_type` (ENG-023): matches
this module's own "Card type: Action" docstring fact above."""


def _has_discipline(state: GameState, vampire: VampireInPlay, discipline: str) -> bool:
    disciplines = effective_disciplines(state, vampire)
    return discipline in disciplines or discipline.upper() in disciplines


def _controllers_vampire(state: GameState, context: Mapping[str, Any]) -> VampireInPlay | None:
    return state.players[context["player"]].vampires.get(context["vampire"])


def _requires_an_anarch(vampire: VampireInPlay | None) -> bool:
    return vampire is not None and vampire.card.sect is Sect.ANARCH


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _eligible_pro_targets(state: GameState, defender: str) -> list[VampireInPlay]:
    """Opponent's own currently-controlled vampires: `"ready"` or
    `"torpor"` (module docstring: torpor still counts as "controlled",
    unlike a face-down `"uncontrolled"` crypt card; a `"burned"`/
    `"removed_from_game"` vampire is no longer controlled by anyone at
    all)."""
    return [v for v in state.players[defender].vampires.values() if v.zone in ("ready", "torpor")]


def _provide_the_platinum_protocol(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    player = context["player"]
    acting_vampire = _controllers_vampire(state, context)
    if not _requires_an_anarch(acting_vampire):
        return []
    has_obf = _has_discipline(state, acting_vampire, OBF)
    has_pre = _has_discipline(state, acting_vampire, PRE)
    has_pro = _has_discipline(state, acting_vampire, PRO)
    if not (has_obf or has_pre or has_pro):
        return []
    if not _has_card_in_hand(state, player):
        return []
    if action_card_already_played_this_turn(state, acting_vampire, NAME):
        return []  # ENG-037 Finding 2: same named action card, once per turn.

    def _apply(s: GameState) -> ActionCardSpec:
        remove_from_hand(s, player, KRCG_ID)

        def resolve(pending: dict[str, Any]) -> None:
            other = s.other_player(player)
            base_amount = (
                BLEED_AMOUNT
                + (PRE_BLEED_BONUS if has_pre else 0)
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
            if has_pro and amount >= 1:
                targets = _eligible_pro_targets(s, other)
                if targets:
                    if len(targets) == 1:
                        target = targets[0]
                    else:
                        choices = tuple(
                            Choice(
                                f"platinum_protocol_target:{v.instance_id}",
                                f"Put 1 corruption counter on {v.card.name}",
                            )
                            for v in targets
                        )
                        decision = Decision(
                            player=player, kind="platinum_protocol_target", choices=choices
                        )
                        chosen_value = s.ask(decision).value
                        chosen_id = chosen_value.split(":", 1)[1]
                        target = next(v for v in targets if v.instance_id == chosen_id)
                    add_corruption_counters(target, placer=player, amount=1)

        return ActionCardSpec(
            base_stealth=STEALTH_BONUS if has_obf else 0,
            directed=True,
            resolve=resolve,
            action=ACTION_BLEED,
            name=NAME,
        )

    parts = ["The Platinum Protocol: Ⓓ Bleed"]
    if has_obf:
        parts.append("[obf] +1 stealth")
    if has_pre:
        parts.append("[pre] +1 bleed")
    if has_pro:
        parts.append("[pro] corruption counter if successful")
    label = ", ".join(parts)

    return [
        HookOption(
            choice=Choice("platinum_protocol", label),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


hooks.register(ACTION_CARD_PLAY_HOOK, _provide_the_platinum_protocol)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.ACTION_CARD_PLAY,),
        source=__name__,
    )
)
