"""Fiorenza Savona (crypt vampire ability). krcg id 201616.

Printed text (verbatim, via the installed `krcg` package's `krcg.vtes.VTES
[201616].card_text`, re-verified live 2026-10-14): "Camarilla: If you burn
the Edge for a vote, you get +1 vote. If you burn a political action card
for a vote, you get +1 vote." No rulings on file (`krcg.vtes.VTES
[201616].rulings == []`). Clan Ventrue, no title, group 6, capacity 7.

ENG-031 (resolved): both sentences modify a
referendum's vote tally conditioned on a *specific other* `VoteSource`
actually being cast by Fiorenza's own controller -- the Edge-burn source
(`VoteSource.burns_edge`) for clause 1, and (2026-10-14 user ruling,
settling ENG-031's own scope sub-question) specifically the non-caller's
political-action-card-from-hand burn (`VoteSource.burns_pac_from_hand`) for
clause 2, never the caller's own political-action-card source (which is
played/shown, not burned). `engine/politics.py::_cast_votes` now dispatches
`VOTE_SOURCE_CAST_BONUS_HOOK` at exactly that moment (`cards/registry.py::
Hook.VOTE_SOURCE_CAST_BONUS`), which this module registers against.

Scope/duration: "you" is whoever *controls* Fiorenza, read off `source.
player` (the Methuselah actually casting that source, matching `VoteSource`
construction in `_collect_vote_sources`), not the referendum's own caller.
No "while ready" qualifier is printed (contrast Carmelita Neillson,
`cards/carmelita_neillson.py`, whose own module docstring explains why its
own zone/locked check exists only because its text says "while ready") --
so this module gates only on Fiorenza being an actual in-play minion of her
controller's (`zone` not `"uncontrolled"` -- not yet revealed into play --
nor `"burned"`/`"removed_from_game"` -- no longer in play at all), never on
`ready`/`locked`/`torpor`, mirroring Marcos Belegrad's own precedent of
adding no extra zone gate beyond "in play" absent explicit text for one.

Both clauses are mutually exclusive on any single cast (`_collect_
vote_sources` never sets both flags on the same `VoteSource`), so a flat
+1 whenever either flag is set, with no summing risk, correctly implements
both sentences with one provider.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.politics import VOTE_SOURCE_CAST_BONUS_HOOK
from vtesbot.engine.state import GameState

KRCG_ID = 201616


def _controls_fiorenza_in_play(state: GameState, player: str) -> bool:
    return any(
        vampire.card.krcg_id == KRCG_ID
        and vampire.zone not in ("uncontrolled", "burned", "removed_from_game")
        for vampire in state.players[player].vampires.values()
    )


def _provide_fiorenza_savona(state: GameState, context: Mapping[str, Any]) -> int:
    if not (context.get("burns_edge") or context.get("burns_pac_from_hand")):
        return 0
    caster = context.get("caster")
    if caster is None or not _controls_fiorenza_in_play(state, caster):
        return 0
    return 1


hooks.register(VOTE_SOURCE_CAST_BONUS_HOOK, _provide_fiorenza_savona)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Fiorenza Savona",
        status=Status.IMPLEMENTED,
        hooks=(Hook.VOTE_SOURCE_CAST_BONUS,),
        source=__name__,
    )
)
