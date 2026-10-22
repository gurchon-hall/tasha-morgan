"""Sakhar (crypt vampire ability). krcg id 201685.

Printed text (fetched via `krcg.load()` + `msgspec.json.encode()`, project's
`uv run` venv (krcg 5.14), 2026-10-17, matching the raw snapshot
`data/cards/201685.json`): "Independent: Sakhar can search your library for
an equipment card, reveal it and move it to your hand as a +1 stealth
action."

Rulings: none on file (`rulings == []`, confirmed in the raw snapshot).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Salubri, group 7,
capacity 6, disciplines `("dom", "AUS", "FOR")`. No title. Legal since
2024-01-31; confirmed on the active 2P allowed list (`data/formats/2p/
2026-10-03.json`) and in the suggested 2P decklist `data/decks/vekn-2p/
salubri.json` (2 copies).

This is Sakhar's own printed ability performed as her one minion action for
the turn (not a library card played from hand), wired against the generic
`engine/phases/minion.py::ACTION_CARD_PLAY_HOOK`/`ActionCardSpec` entry point
(ENG-011) the same way Lucinde, Alastor's
own crypt-text grant consumer (`cards/lucinde_alastor.py`) rides it with no
card played at all (`ActionCardSpec.name` stays `None`): no replacement card
is drawn and the generic "same named action card per turn" cap
(`action_card_already_played_this_turn`) never applies, since nothing is ever
removed from hand.

"+1 stealth action" (bare, no "Ⓓ" marker): undirected, baseline stealth 1 --
same reading `RECRUIT_ALLY_STEALTH`'s/`ATTACHMENT_REMOVAL_STEALTH`'s own
docstrings give the Rulebook default-action-list's identical bare phrasing.

"search your library for an equipment card, reveal it and move it to your
hand": one `HookOption` per `"Equipment"`-typed `LibraryCard` (krcg's own
`types` value, confirmed live, e.g. ".44 Magnum") currently in the acting
player's own library -- naming which specific card is searched for and
revealed at the same moment the ability itself is chosen (Sakhar's own
printed text names no external target/minion, so there is no RUL-007 "terms
fixed at announce" question to resolve about a later choice; unlike
Scouting Mission's superior clause, the identity of the found card *is* the
choice). The actual library removal + hand move is deferred into
`resolve()`, run only if the action is not blocked (Rulebook §4 "Resolve the
Action"); it re-validates the named card is still present by krcg id and
name, folding to a no-op fizzle if not (RUL-007 convention -- not reachable
today, since nothing else in this engine mutates another player's library
mid-action, but kept for consistency with every other bound-at-announce
target in this pool). The card text prints no "shuffle your library
afterward" clause (unlike many real-world VTES search effects), and no
on-file ruling adds one, so none is modelled here (CLAUDE.md "no guessing" --
card text is the top source, and it is silent).

Eligibility: offered only while the acting vampire is this exact printed
Sakhar (`krcg_id == KRCG_ID`) and at least one Equipment-typed card sits in
her controller's own library (never offer a play that cannot resolve,
`cards/line_brawl.py`'s own precedent). `played_card_type` stays at its
default `None`: this option is Sakhar's own printed ability being activated,
not a card being played from hand.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, ActionCardSpec
from vtesbot.engine.state import GameState

KRCG_ID = 201685
EQUIPMENT_CARD_TYPE = "Equipment"
SAKHAR_STEALTH = 1
"""Verbatim "+1 stealth action" (bare): undirected, baseline stealth 1 (see
module docstring)."""


def _eligible_equipment_cards(state: GameState, player: str) -> list[Any]:
    return [card for card in state.players[player].library if card.card_type == EQUIPMENT_CARD_TYPE]


def _provide_sakhar(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    acting_vampire = state.players[player].vampires.get(context["vampire"])
    if acting_vampire is None or acting_vampire.card.krcg_id != KRCG_ID:
        return []

    options: list[HookOption] = []
    for index, card in enumerate(_eligible_equipment_cards(state, player)):
        krcg_id = card.krcg_id
        name = card.name

        def _apply(s: GameState, krcg_id: int = krcg_id, name: str = name) -> ActionCardSpec:
            def resolve(pending: dict[str, Any]) -> None:
                del pending  # no later hook window of its own to feed.
                library = s.players[player].library
                for i, c in enumerate(library):
                    matches = (
                        c.card_type == EQUIPMENT_CARD_TYPE
                        and c.krcg_id == krcg_id
                        and c.name == name
                    )
                    if matches:
                        found = library.pop(i)
                        s.players[player].hand.append(found)
                        s.log.record_event(
                            f"{player} reveals {found.name} (Sakhar's search) and takes it to hand"
                        )
                        return
                # fizzles (RUL-007 convention): the named card left the library
                # by resolve time -- not reachable today, kept for consistency.

            return ActionCardSpec(base_stealth=SAKHAR_STEALTH, directed=False, resolve=resolve)

        options.append(
            HookOption(
                choice=Choice(
                    f"sakhar:{index}:{krcg_id}", f"Sakhar: search your library for {name}"
                ),
                apply=_apply,
            )
        )
    return options


hooks.register(ACTION_CARD_PLAY_HOOK, _provide_sakhar)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Sakhar",
        status=Status.IMPLEMENTED,
        hooks=(Hook.ACTION_CARD_PLAY,),
        source=__name__,
    )
)
