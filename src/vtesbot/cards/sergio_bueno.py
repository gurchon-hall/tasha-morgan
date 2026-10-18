"""Sergio Bueno (crypt vampire ability). krcg id 201662.

Printed text (verbatim, via the project's `uv run` venv (krcg 5.14), fetched
2026-10-18, matching the raw snapshot `data/cards/201662.json` byte-for-byte):
    "Anarch Baron of Santo Domingo: Minions with 1 or more of your corruption
    counters must burn 1 blood or life to attempt to block Sergio."

Rulings (verbatim, via krcg, `data/cards/201662.json`):
    - "The passive ability applies even if the vampire is in torpor."
      [LSJ 20011022] -- moot here: the engine only ever calls `attempt_block`
      with `acting_vampire` set to a ready unlocked vampire performing an
      action in the first place (`engine/phases/minion.py::minion_phase`'s
      own action economy), so Sergio being the acting vampire already
      implies he is not in torpor; nothing in this module's own gating
      checks `zone` at all, so this ruling changes nothing to implement.

Card type: crypt vampire (`types == ["Vampire"]`). Clan Ministry, title
"Baron", group 6, capacity 8, disciplines `("aus", "pot", "OBF", "PRE",
"PRO")`. Legal since 2023-08-31; confirmed on the active 2P allowed list
(`data/formats/2p/2026-10-03.json`) and in the suggested 2P decklist
`data/decks/vekn-2p/ministry.json` (3 copies).

Status: implemented, against `engine/action.py::BLOCK_ATTEMPT_COST_HOOK`/
`BlockAttemptCost` (built this pass -- see that hook's own docstring for why
`block_candidate_predicate`/`BLOCK_CANDIDATE_EXCLUSION_HOOK` did not fit: a
passive crypt ability spanning every action type Sergio performs, not one
action card's own printed text, and a mandatory *paid* cost, not a pure
boolean filter).

The title clause ("Anarch Baron of Santo Domingo") needs no module code:
the vote value a ready Baron contributes is handled generically by
`engine/politics.py::TITLE_VOTES` (`{"Baron": 2, ...}`) for every titled
vampire regardless of sect preamble (same precedent as `cards/leumeah.py`/
`cards/kevin_jackson.py`).

"Minions with 1 or more of your corruption counters" -- "your" is scoped to
Sergio's own controller specifically (contrast Aniel's krcg 201666 unscoped
"1 corruption counter", any placer): the check is `candidate.corruption_
counters.get(sergio_controller, 0) >= 1` (`engine/corruption.py`/
`VampireInPlay.corruption_counters`'s own docstring already anticipates this
exact reading) -- `total_corruption_counters` (a flat sum across every
placer) is the wrong primitive here and is not used.

"must burn 1 blood or life to attempt to block Sergio": the Rulebook
glossary (`data/sources/rulebook/2026-10-09/8-glossaries.md:102`), verbatim,
"Life (also Life Counter): A token representing a retainer's or an ally's
health" -- vampires never have a "life" counter, only blood, so "blood or
life" is the card's own generic phrasing covering every minion type that
could in principle attempt a block (a vampire pays blood; an ally/retainer
would pay life), not a real choice offered to a vampire. Moot regardless:
this engine's block-candidate pool is vampires only (`engine/action.py::
attempt_block`'s `state.ready_unlocked_vampires(defender)`; allies/retainers
cannot attempt a block in this project's current combat scope), so only the
"burn 1 blood" branch is reachable -- `BlockAttemptCost.pay` always deducts
blood, never offering a resource-choice `Decision` (there is none to offer).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import BLOCK_ATTEMPT_COST_HOOK, BlockAttemptCost
from vtesbot.engine.state import GameState

KRCG_ID = 201662
BLOOD_COST = 1
"""Verbatim "must burn 1 blood"."""


def _provide_sergio_bueno_block_attempt_cost(
    state: GameState, context: Mapping[str, Any]
) -> BlockAttemptCost | None:
    """ "Minions with 1 or more of your corruption counters must burn 1
    blood or life to attempt to block Sergio." -- `context["actor"]` is
    Sergio's own controller (Sergio is the attacker being blocked);
    `context["acting_vampire"]` must be this specific printed Sergio Bueno
    (a different vampire's action is unaffected, even if that vampire's own
    controller also happens to be this one)."""
    acting_vampire_id = context["acting_vampire"]
    if acting_vampire_id is None:
        return None
    actor = context["actor"]
    acting_vampire = state.players[actor].vampires.get(acting_vampire_id)
    if acting_vampire is None or acting_vampire.card.krcg_id != KRCG_ID:
        return None
    defender = context["defender"]
    candidate = state.players[defender].vampires.get(context["candidate"])
    if candidate is None:
        return None
    if candidate.corruption_counters.get(actor, 0) < 1:
        return None

    def _pay(s: GameState) -> None:
        del s
        candidate.blood -= BLOOD_COST

    return BlockAttemptCost(can_pay=candidate.blood >= BLOOD_COST, pay=_pay)


hooks.register(BLOCK_ATTEMPT_COST_HOOK, _provide_sergio_bueno_block_attempt_cost)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Sergio Bueno",
        status=Status.IMPLEMENTED,
        hooks=(Hook.BLOCK_ATTEMPT_COST,),
        source=__name__,
    )
)
