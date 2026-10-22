"""Marcos Belegrad (crypt vampire ability). krcg id 201702.

Printed text (fetched via krcg's live API, `https://api.krcg.org/card/201702`,
2026-10-11; raw snapshot `data/cards/201702.json`, cross-checked against
`krcg.vtes.VTES[201702].to_json()["card_text"]`, same wording): "Camarilla
Prince of Bogota: Methuselahs casting (including controlling a minion
casting) votes or ballots against a referendum called by Marcos burn 1 pool
once results are tallied."

Rulings: none on file (`krcg.load()[201702].rulings == []` and the raw API
snapshot's own `"rulings": []`, both checked 2026-10-11).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Toreador, title
Prince, group 7, capacity 8, disciplines `["ani", "AUS", "CEL", "PRE"]`
(Rulebook §4 Politics > Gaining Votes > Titled Vampires: a ready Prince is
already worth 2 votes on its own, via the generic `TITLE_VOTES` table in
`engine/politics.py`; this module only adds the printed ability's *extra*,
distinct effect on top of that).

Timing window: a mandatory, non-chosen reaction "once results are tallied"
-- i.e. strictly after `engine/politics.py::_cast_votes` returns, and before
the referendum's own pass/fail effects take place (matching the card's own
"once results are tallied" wording exactly). This is `engine/politics.py::
REFERENDUM_TALLIED_HOOK` (`cards/registry.py::Hook.REFERENDUM_TALLIED`),
dispatched via `hooks.run_effects` -- there is nothing for a player to
choose (the pool loss is mandatory, not a card the methuselah elects to
play), so no `Decision` is raised; see `engine/politics.py`'s own module
docstring, "A third shape, Marcos Belegrad's...", for why this hook (and not
`sum_modifiers`/`offer`) is the right fit.

Target/scope: "Methuselahs casting ... votes or ballots against a referendum
called by Marcos" -- scoped to referenda called *specifically by this
Marcos instance*, not any referendum this card's controller happens to call
(`engine/politics.py`'s own module docstring, the Queen-Anne/Marcos-Belegrad
discussion of `context["caller_vampire"]`). Checked by
`vampire.card.krcg_id == KRCG_ID` against the live `caller_vampire` the hook
context carries. `context["casts"]` entries are `(source.player,
source.source_id, source.votes, direction)`, where `source.player` is
already "whoever controls that vote source" (`_collect_vote_sources`'s own
`VoteSource(player=player, ...)` construction) -- this is exactly what
"including controlling a minion casting" means, with no special case
needed.

Amount: the printed text says "burn 1 pool" (a flat amount), not "1 pool per
vote" -- nothing scales the loss by how many separate sources or votes a
single Methuselah cast against the referendum. This module therefore
charges exactly 1 pool per *Methuselah* who cast at least one vote or
ballot against Marcos's referendum (not per source, not per vote) -- a
plain reading of the verbatim printed text (CLAUDE.md §2 "Golden Rule for
Cards"), there being no ruling on file either way.

Effect: `lose_pool_simultaneously` (`engine/pool.py`), 1 pool for each such
Methuselah as one event -- floors at 0; a lone Methuselah reduced to 0 is
ousted like any other pool loss, both reduced to 0 tie (DES-010, Rulebook §5).

Fires regardless of the referendum's own eventual pass/fail outcome (the
card's own trigger is "once results are tallied", a moment strictly before
pass/fail is decided at all by `political_action`'s own return value) --
same point the task brief calls out, confirmed by `resolve_referendum`'s own
call order (`_dispatch_referendum_tallied` runs before its `(votes_for,
votes_against, casts)` tuple is handed back to `political_action`, which
only then compares `votes_for > votes_against`).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.politics import VOTE_AGAINST_POOL_COST_HOOK
from vtesbot.engine.pool import lose_pool_simultaneously
from vtesbot.engine.state import GameState

KRCG_ID = 201702
REFERENDUM_TALLIED_HOOK = "referendum_tallied"


def _provide_marcos_belegrad(state: GameState, context: Mapping[str, Any]) -> None:
    caller_vampire = context["caller_vampire"]
    if caller_vampire.card.krcg_id != KRCG_ID:
        return  # not a referendum called by *this* Marcos instance.

    casters_against = {
        player
        for (player, _source_id, _votes, direction) in context["casts"]
        if direction == "against"
    }
    lose_pool_simultaneously(state, dict.fromkeys(casters_against, 1))


def _marcos_against_cost(state: GameState, context: Mapping[str, Any]) -> int:
    """DES-009 (user ruling 2026-10-13): casting against must not be offered
    if the tally burn would take the caster to 0 pool. One burn per
    Methuselah, so a second against-cast costs nothing more."""
    caller_vampire = context["caller_vampire"]
    if caller_vampire is None or caller_vampire.card.krcg_id != KRCG_ID:
        return 0
    player = context["player"]
    if any(p == player and d == "against" for (p, _s, _v, d) in context["casts"]):
        return 0
    return 1


hooks.register(REFERENDUM_TALLIED_HOOK, _provide_marcos_belegrad)
hooks.register(VOTE_AGAINST_POOL_COST_HOOK, _marcos_against_cost)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Marcos Belegrad",
        status=Status.IMPLEMENTED,
        hooks=(Hook.REFERENDUM_TALLIED,),
        source=__name__,
    )
)
