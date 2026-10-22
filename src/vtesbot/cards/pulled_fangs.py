"""Pulled Fangs (Combat). krcg id 101515.

Card text (verbatim, via `krcg.load()` + `msgspec.json.encode()` in the
project's `uv run` virtualenv (krcg 5.14), 2026-10-16, matching the raw
snapshot saved to `data/cards/101515.json`):
    "Only usable at close range at the end of a round during which this
    minion successfully inflicted more damage than the opposing vampire.
    Not usable by a minion being burned or going to torpor.
    Put this card on the opposing vampire; this minion inflicts 1 damage
    on them. The attached vampire cannot hunt; if they must hunt, they go
    to torpor instead. Any vampire(s) can burn this card with two +1
    stealth actions. A vampire can have only one Pulled Fangs."

Rulings (via krcg; citations only):
    - "Counts up damage successfully inflicted during the round ...
      retainers and environmental damage do not count." [TOM 19950304]
      [LSJ 20010812]
    - "Must be played after the presses are handled and can be played if
      the round ends prematurely." [RTR 20030519]
    - "Can be played before or after effects played at the end of the
      round or 'when combat would end' ... Can be played before or after
      [CEL] Psyche!" [LSJ 20021113] [ANK 20191219] [ANK 20180910-1]
    - "A total of two actions must be performed (by whomever) to remove
      it. Vampires A and B can both take the action, then it is removed."
      [ANK 20170202-2]
    - End-of-round range-default ruling [LSJ 20100709]: not card-specific,
      an engine-level fact about range at the end of a *prematurely ended*
      round -- not reachable here since this card requires close range,
      and `GameState.combat_range` is only ever `None` once `run_combat`
      exits entirely, strictly after `END_OF_ROUND_HOOK` has already
      dispatched for the round in progress.

Card type: Combat (`types == ["Combat"]`). No discipline/clan requirement,
`cost is None`. Legal since 1994-09-15; on the active 2P allowed list
(`data/formats/2p/2026-10-03.json`). No Ⓓ/prey/predator/vote wording
(scoped to the current combat's own two combatants); not RUL-001.

Status: implemented, against three primitives built this session:
`engine/damage.py::DAMAGE_SUCCESSFULLY_INFLICTED_KEY`/`damage_
successfully_inflicted_this_round` (the playability trigger), `engine/
phases/minion.py::CANNOT_HUNT_HOOK` (the attached vampire's forced-torpor
clause), and `ATTACHMENT_REMOVAL_ACTION_HOOK`/`build_attachment_removal_
action_spec` (the "burn this card with two +1 stealth actions" clause,
`contributions_required=2` matching this card's own printed "two").

Playability trigger: offered via `END_OF_ROUND_HOOK` (mirrors `taste_of_
vitae.py`'s own "this provider is only ever offered via END_OF_ROUND_HOOK"
reasoning for "only usable at the end of a round"), additionally gated on
`state.combat_range == CLOSE_RANGE` and on `damage_successfully_inflicted_
this_round(round_state, this_vampire) > damage_successfully_inflicted_
this_round(round_state, opposing_vampire)`, recomputed live inside `apply`
(not cached from offer time), same "repeatable window" reasoning as
`taste_of_vitae.py`. "Not usable by a minion being burned or going to
torpor": a zone gate on the *playing* vampire only, mirroring `taste_of_
vitae.py`'s identical clause (the opposing vampire's own zone is
unrestricted).

"A vampire can have only one Pulled Fangs.": read as a cap on the *host*
(the vampire the card is put on, i.e. the opposing vampire here, since
this card is never put on the playing vampire itself) -- not offered if
the opponent already carries a `krcg_id == KRCG_ID`, `zone == "attached"`
copy.

"Put this card on the opposing vampire; this minion inflicts 1 damage on
them.": `attach_card` with `controller` set to the *playing* Methuselah
(not the host's own controller) -- `engine/attachments.py`'s own module
docstring ("controller may differ") anticipates exactly this shape, and
"any vampire(s) can burn this card" below is explicitly controller-
agnostic, consistent with this attachment not being controlled by its
host. The 1 damage is `apply_damage(..., inflicted_by=<this vampire>)`,
recorded into the same round's `round_state` for consistency with every
other `apply_damage` call site, though no card text depends on it being
counted again this same round.

"The attached vampire cannot hunt; if they must hunt, they go to torpor
instead.": `CANNOT_HUNT_HOOK`, gated on the host vampire carrying a live
Pulled Fangs attachment.

"Any vampire(s) can burn this card with two +1 stealth actions.":
`ATTACHMENT_REMOVAL_ACTION_HOOK`, offered for every acting vampire of
either player while a live Pulled Fangs attachment exists anywhere in
play, one option per live attachment instance (the printed cap means
there is normally at most one attached to any single vampire at a time,
but two separate host vampires could each carry their own copy).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.attachments import attach_card, iter_attachments
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.combat import CLOSE_RANGE, END_OF_ROUND_HOOK, ROUND_STATE_CONTEXT_KEY
from vtesbot.engine.damage import apply_damage, damage_successfully_inflicted_this_round
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import (
    ATTACHMENT_REMOVAL_ACTION_HOOK,
    CANNOT_HUNT_HOOK,
    build_attachment_removal_action_spec,
)
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101515
NAME = "Pulled Fangs"
DAMAGE_AMOUNT = 1
"""Verbatim "this minion inflicts 1 damage on them."."""
CONTRIBUTIONS_REQUIRED = 2
"""Verbatim "burn this card with two +1 stealth actions."."""
_EXCLUDED_ZONES = ("burned", "torpor")
CARD_TYPE = "Combat"
"""`HookOption.played_card_type` (ENG-023): matches this module's own "Card
type: Combat" docstring fact above."""


def _combatants(context: Mapping[str, Any]) -> tuple[str, str, str, str]:
    """ "This minion"/"the opposing vampire" resolved against `END_OF_ROUND_
    HOOK`'s own absolute (not `vampire`/`opponent`-relative) context, same
    convention `taste_of_vitae.py` already uses. Returns `(player, vampire_
    id, opponent_player, opponent_vampire_id)`."""
    player = context["player"]
    if player == context["acting_player"]:
        vampire_id = context["acting_vampire"]
        opponent_player = context["blocking_player"]
        opponent_id = context["blocking_vampire"]
    else:
        vampire_id = context["blocking_vampire"]
        opponent_player = context["acting_player"]
        opponent_id = context["acting_vampire"]
    return player, vampire_id, opponent_player, opponent_id


def _has_attached_pulled_fangs(vampire: VampireInPlay) -> bool:
    return any(a.krcg_id == KRCG_ID and a.zone == "attached" for a in vampire.attachments)


def _provide_pulled_fangs(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player, vampire_id, opponent_player, opponent_id = _combatants(context)
    vampire = state.players[player].vampires.get(vampire_id)
    opponent = state.players[opponent_player].vampires.get(opponent_id)
    if vampire is None or opponent is None:
        return []
    if vampire.zone in _EXCLUDED_ZONES:
        return []  # "Not usable by a minion being burned or going to torpor."
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []
    if state.combat_range != CLOSE_RANGE:
        return []  # "Only usable at close range ..."
    if _has_attached_pulled_fangs(opponent):
        return []  # "A vampire can have only one Pulled Fangs."

    round_state = context.get(ROUND_STATE_CONTEXT_KEY)
    inflicted = damage_successfully_inflicted_this_round(round_state, vampire_id)
    opposing_inflicted = damage_successfully_inflicted_this_round(round_state, opponent_id)
    if inflicted <= opposing_inflicted:
        return []  # "... during which this minion successfully inflicted more damage ..."

    def _apply(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)  # no block window: straight to the ash heap.
        live_opponent = s.players[opponent_player].vampires.get(opponent_id)
        if live_opponent is None:
            return  # fizzles (RUL-007 convention): the opposing vampire left play since offer.
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
        HookOption(
            choice=Choice(
                "pulled_fangs",
                f"Pulled Fangs: attach to {opponent.card.name}, inflict {DAMAGE_AMOUNT} damage",
            ),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


def _provide_cannot_hunt(state: GameState, context: Mapping[str, Any]) -> bool:
    """ "The attached vampire cannot hunt ..." """
    vampire = state.players[context["player"]].vampires.get(context["vampire"])
    if vampire is None:
        return False
    return _has_attached_pulled_fangs(vampire)


def _live_pulled_fangs_attachments(state: GameState) -> list[tuple[VampireInPlay, CardAttachment]]:
    return [
        (host, attachment)
        for host, attachment in iter_attachments(state)
        if attachment.krcg_id == KRCG_ID and attachment.zone == "attached"
    ]


def _provide_attachment_removal(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "Any vampire(s) can burn this card with two +1 stealth actions." --
    one option per live Pulled Fangs attachment, offered to the current
    acting vampire regardless of controller or host (no restriction in the
    printed text on who may contribute)."""
    del context  # unrestricted: every acting vampire sees the same options.

    def _make_apply(attachment: CardAttachment) -> Any:
        def _apply(s: GameState) -> Any:
            del s
            return build_attachment_removal_action_spec(
                attachment, contributions_required=CONTRIBUTIONS_REQUIRED
            )

        return _apply

    return [
        HookOption(
            choice=Choice(
                f"pulled_fangs:remove:{attachment.instance_id}",
                f"Pulled Fangs: contribute to burning (attached to {host.card.name})",
            ),
            apply=_make_apply(attachment),
        )
        for host, attachment in _live_pulled_fangs_attachments(state)
    ]


hooks.register(END_OF_ROUND_HOOK, _provide_pulled_fangs)
hooks.register(CANNOT_HUNT_HOOK, _provide_cannot_hunt)
hooks.register(ATTACHMENT_REMOVAL_ACTION_HOOK, _provide_attachment_removal)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.END_OF_ROUND, Hook.CANNOT_HUNT, Hook.ATTACHMENT_REMOVAL_ACTION_PLAY),
        source=__name__,
    )
)
