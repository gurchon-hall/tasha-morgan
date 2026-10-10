"""Celerity (Master: Discipline). krcg id 100312.

Card text (verified live via `krcg.load()[100312]`, 2026-10-09, matching the
raw snapshot `data/cards/100312.json`):
    "Discipline.
    Put this card on a vampire. This vampire gets +1 level of Celerity [cel]
    and +1 capacity. Cannot be put on a vampire with superior Celerity
    [CEL]."

Rulings: none on file -- `krcg.load()[100312].rulings == []`.

Card type: Master. `discipline_requirement.disciplines == []`,
`clan_requirement == []`, `cost is None` (free to play), `trifle is False`
(an ordinary, single master-phase action -- unlike the trifle Life in the
City, playing this does *not* grant an extra master phase action).

Timing window: master phase action (`"master_phase_play"` hook, wired in
`engine/phases/master.py`, same pattern as `life_in_the_city.py`).

Target ("a vampire", no "you control" qualifier): Rulebook SS2 Card Types
"A master card in play is controlled by the Methuselah who played it, even
if it is played on a card controlled by another Methuselah" -- general
master cards, including the "Discipline" subtype this card belongs to
("Disciplines: A Discipline card is played on a controlled vampire...",
same section), may target either player's vampire. "Controlled" here tracks
the Rulebook SS8 glossary "Target" rule: "If a card is played on another
card, or targets another card, the target card must be in play (that is,
controlled). Vampires in the torpor region are eligible targets by default,
but vampires in the uncontrolled region and contested cards are not." So the
legal target pool is every vampire with `zone in {"ready", "torpor"}`,
either player's -- never an uncontrolled (face-down) vampire.

"Cannot be put on a vampire with superior Celerity [CEL]": a target-legality
filter against the vampire's *effective* discipline levels (OQ-8,
`docs/OPEN_QUESTIONS.md`; `engine/attachments.py::effective_disciplines`),
not merely its printed ones -- a vampire who reached effective superior
Celerity via an earlier-attached copy of this same card must be excluded
exactly like one with printed superior Celerity.

"+1 level of Celerity [cel]" / "+1 capacity": two passive, mandatory,
attachment-sourced bonuses (OQ-8) -- `"capacity_modifier"`
(`hooks.sum_modifiers`) and `"discipline_level_modifier"`
(`hooks.union_modifiers`). Nothing in the printed text marks this card
"unique", and the restriction clause only excludes a vampire *already at*
effective superior Celerity -- not a vampire with one copy already
attached at basic -- so a second copy may legally be attached to the same
vampire, stacking the level from none -> basic -> superior exactly as the
restriction clause's own existence implies (it would otherwise never have
anything to guard against for a vampire with no printed Celerity at all).
The discipline-level provider therefore counts every attached copy of this
card on the vampire, adds it to the vampire's *printed* Celerity level, and
caps the result at superior (there is no level beyond it) -- not a new
guess, a direct, literal application of "+1 level ... per copy attached"
with the one explicit cap the card text itself states. The capacity bonus
(`sum_modifiers`) already adds correctly per attached copy with no special
handling needed.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.attachments import effective_disciplines
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 100312
MASTER_PHASE_PLAY_HOOK = "master_phase_play"
CAPACITY_MODIFIER_HOOK = "capacity_modifier"
DISCIPLINE_LEVEL_MODIFIER_HOOK = "discipline_level_modifier"
SUPERIOR = "CEL"
BASIC = "cel"


def _find_vampire(state: GameState, vampire_id: str) -> VampireInPlay | None:
    for player_state in state.players.values():
        vampire = player_state.vampires.get(vampire_id)
        if vampire is not None:
            return vampire
    return None


def _attached_copies(vampire: VampireInPlay) -> int:
    return sum(1 for a in vampire.attachments if a.krcg_id == KRCG_ID)


def _eligible_targets(state: GameState) -> list[VampireInPlay]:
    targets: list[VampireInPlay] = []
    for player_state in state.players.values():
        for vampire in player_state.vampires.values():
            if vampire.zone not in ("ready", "torpor"):
                continue  # uncontrolled vampires are not eligible targets by default.
            if SUPERIOR in effective_disciplines(state, vampire):
                continue  # "Cannot be put on a vampire with superior Celerity [CEL]".
            targets.append(vampire)
    return targets


def _provide_celerity(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    targets = _eligible_targets(state)
    if not targets:
        return []

    options: list[HookOption] = []
    for vampire in targets:

        def _apply(s: GameState, vampire: VampireInPlay = vampire) -> bool:
            play_from_hand(s, player, KRCG_ID)
            vampire.attachments.append(CardAttachment(krcg_id=KRCG_ID, name="Celerity"))
            return False  # not a trifle: no extra master phase action.

        options.append(
            HookOption(
                choice=Choice(
                    f"celerity:{vampire.instance_id}",
                    f"Celerity: attach to {vampire.card.name} ({vampire.controller})",
                ),
                apply=_apply,
            )
        )
    return options


def _provide_capacity_bonus(state: GameState, context: Mapping[str, Any]) -> int:
    vampire = _find_vampire(state, context["vampire"])
    if vampire is None:
        return 0
    return _attached_copies(vampire)  # "+1 capacity" per attached copy.


def _provide_discipline_level(state: GameState, context: Mapping[str, Any]) -> tuple[str, ...]:
    vampire = _find_vampire(state, context["vampire"])
    if vampire is None:
        return ()
    copies = _attached_copies(vampire)
    if copies == 0:
        return ()
    printed = vampire.card.disciplines
    printed_level = 2 if SUPERIOR in printed else 1 if BASIC in printed else 0
    total = min(2, printed_level + copies)
    return (SUPERIOR,) if total == 2 else (BASIC,)


hooks.register(MASTER_PHASE_PLAY_HOOK, _provide_celerity)
hooks.register(CAPACITY_MODIFIER_HOOK, _provide_capacity_bonus)
hooks.register(DISCIPLINE_LEVEL_MODIFIER_HOOK, _provide_discipline_level)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Celerity",
        status=Status.IMPLEMENTED,
        hooks=(Hook.MASTER_PHASE_PLAY, Hook.CAPACITY_MODIFIER, Hook.DISCIPLINE_LEVEL_MODIFIER),
        source=__name__,
    )
)
