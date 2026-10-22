"""Aniel (crypt vampire ability). krcg id 201666.

Printed text (fetched via `krcg.load()` + `msgspec.json.encode()`, project's
`uv run` venv (krcg 5.14), 2026-10-17, matching the raw snapshot
`data/cards/201666.json`): "Independent: Aniel can burn 1 corruption counter
or a card requiring a Discipline from another ready minion as a +1 stealth Ⓓ
action that costs 1 blood."

Rulings: none on file (`rulings == []`, confirmed in the raw snapshot).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Salubri, group 7,
capacity 6, disciplines `("for", "AUS", "DOM")`. No title. Legal since
2024-01-31; confirmed on the active 2P allowed list (`data/formats/2p/
2026-10-03.json`) and in the suggested 2P decklist `data/decks/vekn-2p/
salubri.json` (2 copies).

Status: implemented (ENG-042 resolved). Wired against `engine/phases/
minion.py::ACTION_CARD_PLAY_HOOK`: the corruption-counter half burns
directly off the targeted `VampireInPlay.corruption_counters`
(`engine/corruption.py`, not an attachment -- see that field's own
docstring and this module's own correction below), and the
discipline-requiring-card half mirrors `cards/weighted_walking_stick.py`'s
own counter-bearing-attachment-zone convention. Cost (1 blood) and the
actual burn both happen inside `resolve()`, so a blocked attempt pays
nothing and burns nothing (Rulebook §4 Detailed Turn Sequence: "the cost of
the action is paid... only if the action succeeds").

"Ⓓ action": Rulebook §8 Glossary "Directed Action" (`data/sources/rulebook/
2026-10-09/8-glossaries.md:59`), verbatim: "An action of one Methuselah's
minion that targets one or more other Methuselahs, or the minions or cards
they control." -- the printed Ⓓ marker itself settles that "another ready
minion" is restricted to the *opponent's* ready minion here (in a 2P duel,
the sole other Methuselah, CLAUDE.md §3); it cannot be Aniel's own
controller's other minions, since that would not be a directed action at
all. No RUL entry: this is a direct reading of the glossary definition,
not a guess.

"ready minion": §8 Glossary "Ready Region: Area containing a Methuselah's
minions that are not in torpor" -- `zone == "ready"`, independent of the
`locked` flag (confirmed precedent: `cards/life_in_the_city.py`'s own
identical reading for "a ready vampire"). Only vampires can carry a
`CardAttachment` in this engine (`VampireInPlay.attachments`; allies/retainers
have none), so the target pool is the opponent's `zone == "ready"` vampires.

"burn 1 corruption counter ... from another ready minion": the counter lives
on the targeted vampire itself, not on any attachment (`VampireInPlay.
corruption_counters`, `engine/corruption.py` -- every legal-2P card printing
this keyword puts the counter on the minion, confirmed across Aniel, Sergio
Bueno (201662) and The Platinum Protocol (102232), see that field's own
docstring). "1 corruption counter" with no placer qualifier (contrast Sergio
Bueno's own "YOUR corruption counters") reads as *any* counter present,
regardless of who placed it -- one option per placer with at least 1 counter
on that vampire (`_corruption_counter_placers`), each burning via
`engine/corruption.py::burn_corruption_counters`. In a 2P duel there is at
most one placer in practice (the opponent, i.e. Aniel's own controller, since
no implemented card lets a controller place a corruption counter on their
own vampire) -- see `_corruption_counter_placers`'s own docstring.

"or a card requiring a Discipline ... from another ready minion": any
attachment on that vampire with `zone == "attached"` and `requires_
discipline` (ENG-042, `engine/cards.py::CardAttachment`) is burned outright --
`zone = "burned"`, left in `vampire.attachments` (mirrors `engine/
attachments.py::resolve_one_attachment_contest`'s own "zone=burned, stays in
the list, other providers filter on `zone == "attached"`" convention, not
`cards/weighted_walking_stick.py`'s own `list.remove()` exception, which is
that card's own degrade-to-nothing rule). Every attaching card implemented
today (Celerity, Fame, Perfectionist, Pulled Fangs, Weighted Walking Stick)
prints `discipline_requirement.disciplines == []` (re-verified 2026-10-17,
`data/cards/100312.json`/`100698.json`/`101388.json`/`101515.json`/
`102169.json`), so none of them ever actually sets `requires_discipline=True`
-- this branch is therefore not reachable through any currently-implemented
attaching card, proven instead via `tests/cards/test_aniel.py`'s own directly
constructed `CardAttachment(requires_discipline=True, ...)`, the same
"generic primitive, currently-unreachable in practice" shape `cards/
opikun.py`'s own docstring already accepts for its own Skin-of-Night corner
case.

"Aniel can burn ... as a ... action that costs 1 blood": the cost is paid
from Aniel's own blood pool (no "from this vampire" qualifier ties it to the
target; mirrors `cards/opikun.py`'s own "named ability-user pays their own
cost" reading, Rulebook §2 "Costs are paid from own resources only") --
gated on `aniel.blood >= 1`; not offered below that.

"+1 stealth Ⓓ action": baseline stealth 1, `directed=True` (see above).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.corruption import burn_corruption_counters
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, ActionCardSpec
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 201666
ANIEL_STEALTH = 1
"""Verbatim "+1 stealth Ⓓ action": directed, baseline 1."""
BLOOD_COST = 1
"""Verbatim "costs 1 blood"."""


def _controlled_anielid_vampires(state: GameState, player: str) -> list[VampireInPlay]:
    return [
        v
        for v in state.players[player].vampires.values()
        if v.card.krcg_id == KRCG_ID and v.zone in ("ready", "torpor")
    ]


def _opponent_ready_vampires(state: GameState, player: str) -> list[VampireInPlay]:
    opponent = state.other_player(player)
    return [v for v in state.players[opponent].vampires.values() if v.zone == "ready"]


def _live_attachments(vampire: VampireInPlay) -> list[CardAttachment]:
    return [a for a in vampire.attachments if a.zone == "attached"]


def _corruption_counter_placers(vampire: VampireInPlay) -> list[str]:
    """Every Methuselah with at least 1 corruption counter on `vampire`
    (`VampireInPlay.corruption_counters`, `engine/corruption.py`). Today
    this is at most the single opponent in a 2P duel -- no implemented
    card lets a controller place a corruption counter on their own
    vampire -- but a separate option per placer is still the correct
    shape (not a hardcoded pick), since which placer's stash is burned
    changes a later "YOUR corruption counters" check (Sergio Bueno, krcg
    201662, `cards/sergio_bueno.py`). Mirrors `cards/opikun.py`'s own
    "generic primitive, currently-unreachable in practice" precedent."""
    return [placer for placer, count in vampire.corruption_counters.items() if count > 0]


def _counter_burn_option(aniel: VampireInPlay, vampire: VampireInPlay, placer: str) -> HookOption:
    label = f"Aniel: burn 1 corruption counter ({placer}'s) on {vampire.card.name}"

    def _apply(s: GameState) -> ActionCardSpec:
        def resolve(pending: dict[str, Any]) -> None:
            del pending
            if burn_corruption_counters(vampire, placer, 1) <= 0:
                return  # RUL-007 convention: fizzles if gone by resolve time.
            aniel.blood -= BLOOD_COST
            s.log.record_event(f"Aniel burns 1 corruption counter on {vampire.card.name}")

        return ActionCardSpec(base_stealth=ANIEL_STEALTH, directed=True, resolve=resolve)

    return HookOption(
        choice=Choice(
            f"aniel:counter:{aniel.instance_id}:{vampire.instance_id}:{placer}",
            label,
        ),
        apply=_apply,
    )


def _discipline_card_burn_option(
    aniel: VampireInPlay, vampire: VampireInPlay, attachment: CardAttachment
) -> HookOption:
    label = f"Aniel: burn {attachment.name} (requires a Discipline) from {vampire.card.name}"

    def _apply(s: GameState) -> ActionCardSpec:
        def resolve(pending: dict[str, Any]) -> None:
            del pending
            if attachment.zone != "attached":
                return  # RUL-007 convention: fizzles if gone by resolve time.
            aniel.blood -= BLOOD_COST
            attachment.zone = "burned"
            s.log.record_event(f"Aniel burns {attachment.name} from {vampire.card.name}")

        return ActionCardSpec(base_stealth=ANIEL_STEALTH, directed=True, resolve=resolve)

    return HookOption(
        choice=Choice(
            f"aniel:discipline:{aniel.instance_id}:{vampire.instance_id}:{attachment.instance_id}",
            label,
        ),
        apply=_apply,
    )


def _provide_aniel(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    acting_vampires = {v.instance_id for v in _controlled_anielid_vampires(state, player)}
    if context["vampire"] not in acting_vampires:
        return []
    aniel = state.players[player].vampires[context["vampire"]]
    if aniel.blood < BLOOD_COST:
        return []

    options: list[HookOption] = []
    for vampire in _opponent_ready_vampires(state, player):
        for placer in _corruption_counter_placers(vampire):
            options.append(_counter_burn_option(aniel, vampire, placer))
        for attachment in _live_attachments(vampire):
            if attachment.requires_discipline:
                options.append(_discipline_card_burn_option(aniel, vampire, attachment))
    return options


hooks.register(ACTION_CARD_PLAY_HOOK, _provide_aniel)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Aniel",
        status=Status.IMPLEMENTED,
        hooks=(Hook.ACTION_CARD_PLAY,),
        source=__name__,
    )
)
