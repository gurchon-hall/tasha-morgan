"""Perfectionist (Master, Archetype). krcg id 101388.

Card text (verbatim, via `krcg.load()` + `msgspec.json.encode()` in the
project's `uv run` virtualenv (krcg 5.14), 2026-10-15, matching the raw
snapshot saved to `data/cards/101388.json`):
    "Archetype.
    Put this card on a vampire you control. Once each turn, this vampire
    can gain 1 blood after performing a successful action during which no
    reaction cards were played. A vampire can have only one archetype."

Rulings (verbatim, via krcg; `cards["Perfectionist"].rulings`):
    - "No blood can be gained if a reaction card is played and canceled as
      it is played: it has still been played." [LSJ 20070330]
    - "Cards and effects that can be played 'after resolution' can be
      played after the gain blood effect." [ANK 20190113]
    - "The blood can be gained if the action is unblocked even if it has no
      effect (due to lack of a suitable target, for example)."
      [LSJ 20070411]
    - "'Once each turn' means once during each player's turn."
      [ANK 20180719-4]
    - "The vampire's controller chooses to use the effect of the card or
      not." [ANK 20210309-3]

Card type: Master. `cost is None`, `trifle is False`, not printed
"Unique" -- an ordinary, free master-phase play. Legal since 2004-06-16;
on the active 2P allowed list (`data/formats/2p/2026-10-03.json`).

"After performing a successful action": per Rulebook §4 "Resolve the
Action" step 3 and the "Political Action"/"Referendum" entries, a
political action's success is "unblocked", independent of whether the
referendum it calls later passes or fails -- the pass/fail outcome is a
later, separate step. The provider below dispatches off
`ACTION_SUCCEEDED_HOOK` only, never reading `REFERENDUM_RESULT_KEY`.

Status: implemented.

Attach clause ("Put this card on a vampire you control... A vampire can
have only one archetype"): `engine/attachments.py::attach_card`, no
contest machinery (not "Unique"), gated on the target not already
carrying a Perfectionist (the only Archetype card in this pool). Target
pool is "a vampire you control" with no zone qualifier -- Rulebook §8
glossary "Target": `zone in ("ready", "torpor")` (torpid is eligible,
uncontrolled is not; same reading `fame.py`/`lucinde_alastor.py` give the
identical unqualified wording).

Blood-gain clause: registered on `ACTION_SUCCEEDED_HOOK`
(`engine/action.py`), whose own context carries the acting
`VampireInPlay` and the action's `pending` dict. Gated, in order: (1) the
acting vampire itself carries an attached (`zone == "attached"`)
Perfectionist -- "this vampire" is the one performing the action, same
object identity, no separate target lookup; (2) not already used this
turn (`VampireInPlay.ability_used_turn`, `lucinde_alastor.py`'s
once-per-turn convention, per [ANK 20180719-4]); (3)
`pending.get(hooks.PENDING_REACTION_PLAYED_KEY, False)` is falsy ([LSJ
20070330]: a card canceled as played still counts as played, already
captured by that flag). When all three hold, a `Decision` offers
"gain"/"decline" to the vampire's own controller ([ANK 20210309-3]: the
choice is the controller's, not automatic); `ability_used_turn` is only
set on "gain", so a decline leaves the opportunity open for a later
successful action the same turn. [ANK 20190113] (post-resolution plays)
and [LSJ 20070411] (no-effect actions still qualify) need no code: the
former has no "after resolution" window modeled yet in this project
(same "unreachable today" note as `scalpel_tongue.py`'s own on-file
ruling), and the latter already holds by construction -- the hook fires
regardless of what `resolve()` did.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import ACTION_SUCCEEDED_HOOK
from vtesbot.engine.attachments import attach_card
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.damage import add_blood
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.master import MASTER_PHASE_PLAY_HOOK
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101388
CARD_TYPE = "Master"
ABILITY_USED_KEY = "perfectionist_gain_blood"
"""`VampireInPlay.ability_used_turn` key: once-per-turn cap (module
docstring, [ANK 20180719-4])."""
IN_PLAY_ZONES = ("ready", "torpor")
"""Rulebook §8 glossary "Target": "a vampire you control" with no zone
qualifier admits torpid, excludes uncontrolled (module docstring)."""


def _active_perfectionist_attachment(vampire: VampireInPlay) -> CardAttachment | None:
    for attachment in vampire.attachments:
        if attachment.krcg_id == KRCG_ID and attachment.zone == "attached":
            return attachment
    return None


def _eligible_attach_targets(state: GameState, player: str) -> list[VampireInPlay]:
    """ "Put this card on a vampire you control"; "a vampire can have only
    one archetype" excludes a vampire that already carries one (module
    docstring)."""
    return [
        v
        for v in state.players[player].vampires.values()
        if v.zone in IN_PLAY_ZONES and _active_perfectionist_attachment(v) is None
    ]


def _provide_perfectionist_master_phase_play(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    player = context["player"]
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []
    targets = _eligible_attach_targets(state, player)
    if not targets:
        return []  # never offer a play that cannot resolve.

    options: list[HookOption] = []
    for vampire in targets:

        def _apply(s: GameState, vampire: VampireInPlay = vampire) -> bool:
            play_from_hand(s, player, KRCG_ID)
            attach_card(s, vampire, controller=player, krcg_id=KRCG_ID, name="Perfectionist")
            return False  # not a trifle: no extra master phase action.

        options.append(
            HookOption(
                choice=Choice(
                    f"perfectionist:{vampire.instance_id}",
                    f"Perfectionist: attach to {vampire.card.name}",
                ),
                apply=_apply,
                played_card_type=CARD_TYPE,
            )
        )
    return options


def _provide_perfectionist_blood_gain(state: GameState, context: Mapping[str, Any]) -> None:
    """ "Once each turn, this vampire can gain 1 blood after performing a
    successful action during which no reaction cards were played." --
    offers a `Decision`, per [ANK 20210309-3] (module docstring)."""
    vampire: VampireInPlay = context["vampire"]
    if _active_perfectionist_attachment(vampire) is None:
        return
    if vampire.ability_used_turn.get(ABILITY_USED_KEY) == state.turn_number:
        return
    pending = context.get("pending")
    reaction_played = (
        bool(pending.get(hooks.PENDING_REACTION_PLAYED_KEY, False)) if pending else False
    )
    if reaction_played:
        return  # [LSJ 20070330]: no blood can be gained at all this action.

    decision = Decision(
        player=vampire.controller,
        kind="perfectionist_gain_blood",
        choices=(
            Choice("gain", "Perfectionist: gain 1 blood"),
            Choice("decline", "Decline"),
        ),
        context=hooks.sanitize_decision_context({"vampire": vampire.instance_id}),
    )
    answer = state.ask(decision)
    if answer.value == "gain":
        vampire.ability_used_turn[ABILITY_USED_KEY] = state.turn_number
        add_blood(state, vampire, 1)


hooks.register(MASTER_PHASE_PLAY_HOOK, _provide_perfectionist_master_phase_play)
hooks.register(ACTION_SUCCEEDED_HOOK, _provide_perfectionist_blood_gain)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Perfectionist",
        status=Status.IMPLEMENTED,
        hooks=(Hook.MASTER_PHASE_PLAY, Hook.ACTION_SUCCEEDED),
        source=__name__,
    )
)
