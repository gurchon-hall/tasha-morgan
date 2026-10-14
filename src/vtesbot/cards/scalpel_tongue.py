"""Scalpel Tongue (Action Modifier / Reaction). krcg id 101686.

Card text (verbatim, via krcg 5.14+, `krcg.load()[101686].text`, 2026-10-13):
    "Only usable during the polling step of a political action.
    [cel][pre] Choose a vampire who has cast votes or ballots in this
    referendum. The chosen vampire is locked and abstains (this cancels the
    chosen vampire's votes and ballots).
    [CEL][PRE] As above, and the chosen vampire burns 1 blood."

Ruling (verbatim, via krcg):
    - "Cannot be used during a referendum that is automatically passing."
      [PIB 20150105] [LSJ 19980107]

`types == ["Action Modifier", "Reaction"]`; `disciplines == ["cel", "pre"]`
with `combo == True` (confirmed live, `krcg.load()[101686].combo`) -- unlike
a multi-Discipline "choose any one" card (e.g. `dust_up.py`'s `[ani]`/`[cel]`/
`[pot]`, `multidisc == True`), this card requires *both* listed Disciplines
together at the same level for either clause: basic `[cel][pre]` needs basic
(or better) Celerity *and* basic (or better) Presence on the same vampire;
superior `[CEL][PRE]` needs superior Celerity *and* superior Presence. No
existing card module in this pool has this "combo" shape yet, so there is no
established gating helper to reuse; the two checks below (`_controls_basic_
vampire`/`_controls_superior_vampire`) are this card's own. `clans == []`
(no clan requirement).

`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`) is set to
`"Action Modifier"`, not the full dual-type text: `decks/loader.py::
_build_library_card` derives `LibraryCard.card_type` as `card.types[0].value`
(krcg's own type order), and that module's own docstring asserts every 2P
library card prints exactly one krcg type -- found false for this card while
implementing it (two types, `combo`-gated multi-Discipline), a pre-existing
loader simplification this module does not fix (out of `card-implementer`
scope; flagged for whoever revisits `decks/loader.py`). Matching that same
derivation keeps `played_card_type` consistent with however a deck-imported
copy of this card would actually compare, even though it under-describes the
real printed type; not load-bearing today regardless, since the dispatch
path below (`engine/politics.py::_cast_votes`) never routes a `"mid_cast"`
choice through `apply_chosen_option`/`CANCEL_AS_PLAYED_HOOK` at all (see
that function's own docstring) -- only `offer_until_pass`/
`resolve_impulse_window` do.

Status: implemented (OQ-37, `docs/OPEN_QUESTIONS.md`, resolved --
`engine/politics.py::_cast_votes` now also offers `POLLING_STEP_HOOK` under
`context["phase"] == "mid_cast"`, merged into each player's own
`"polling_step_cast"` turn, whose own `apply(state)` contract returns the
canceled `VoteSource.source_id` rather than `None`).

"Choose a vampire who has cast votes or ballots in this referendum" --
narrowed to `f"title:{vampire.instance_id}"`-sourced casts only, per
`_cast_votes`'s own docstring: a `political_action_card`/
`political_action_card_hand`/`edge` source is tied to a specific
*Methuselah*, not a specific minion, so there is no vampire for this card's
own wording to resolve to for those sources -- not a guess, this is the only
reading the engine's existing vote-source model can support without
inventing an identity the model does not carry. `context["casts"]` (the
snapshot `_cast_votes` already passes) is filtered to `"title:"`-prefixed
entries; the targeted vampire is looked up via that entry's own `player`
(the cast tuple's first element -- its controller) and the instance id
parsed out of the source id.

Who may play it: either Methuselah, independent of who called the
referendum -- the card names no caller/defender restriction, and
`_cast_votes`'s own per-turn rotation (OQ-20) already offers `context["player"]`
in strict alternation regardless of role, so this module's own gate is
purely "does `context['player']` control a ready, unlocked [cel][pre] (or
[CEL][PRE]) vampire, and hold the card in hand" (mirrors
`voter_captivation.py`'s per-player eligibility shape, plus the
`is_ready_unlocked` gate `telepathic_counter.py` already uses -- `rules-
auditor` finding: an earlier draft of this module checked only `zone ==
"ready"`, which would have let a *locked* vampire play this card's Reaction
half, contra the glossary's "a ready unlocked minion can play a reaction
card"). The vampire that *plays* this card is otherwise irrelevant to its
effect (unlike Voter Captivation's "this vampire" clause) -- only its
existence/discipline/readiness is checked, no
specific one is chosen or recorded.

"The chosen vampire is locked and abstains (this cancels the chosen
vampire's votes and ballots)": two separate effects, per OQ-37's own
docstring -- `_apply_retroactive_vote_cancellation` (generic, engine-side)
handles "abstains"/cancels the votes once this module's own `apply` returns
the targeted `source_id`; `apply` itself sets `VampireInPlay.locked = True`
directly, the half the generic mechanism explicitly leaves to the card.

"[CEL][PRE] ... the chosen vampire burns 1 blood": floors at 0 (burning more
blood than present is simply all it has, same convention as `engine/
politics.py::_collect_vote_sources`'s "no negative" invariants elsewhere;
not itself re-sourced by any on-file ruling for this card).

"Cannot be used during a referendum that is automatically passing": not
gated in code -- this engine has no automatically-passing mechanism yet
(`docs/OPEN_QUESTIONS.md` OQ-6's own note, same "unreachable today, not a
dropped ruling" precedent `perfect_paragon.py`/`voter_captivation.py`
already document for their own identical on-file ruling).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.politics import POLLING_STEP_HOOK
from vtesbot.engine.state import GameState

KRCG_ID = 101686
CEL_BASIC = "cel"
CEL_SUPERIOR = "CEL"
PRE_BASIC = "pre"
PRE_SUPERIOR = "PRE"
BURN_AMOUNT = 1
"""Printed "[CEL][PRE] ... the chosen vampire burns 1 blood."."""
CARD_TYPE = "Action Modifier"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): see
module docstring for why this is the first (not the only) printed type."""


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _controls_basic_vampire(state: GameState, player: str) -> bool:
    """ "[cel][pre]" (module docstring, `combo == True`): at least one ready,
    unlocked vampire (Rulebook SS2 Card Types glossary: "A ready unlocked
    minion can play a reaction card" -- this card's Reaction half, same
    `is_ready_unlocked` gate `telepathic_counter.py` already uses) with
    *both* basic-or-better Celerity and basic-or-better Presence."""
    return any(
        v.is_ready_unlocked
        and (CEL_BASIC in v.card.disciplines or CEL_SUPERIOR in v.card.disciplines)
        and (PRE_BASIC in v.card.disciplines or PRE_SUPERIOR in v.card.disciplines)
        for v in state.players[player].vampires.values()
    )


def _controls_superior_vampire(state: GameState, player: str) -> bool:
    """ "[CEL][PRE]": at least one ready, unlocked vampire (see
    `_controls_basic_vampire`'s own docstring for the `is_ready_unlocked`
    gate) with *both* superior Celerity and superior Presence."""
    return any(
        v.is_ready_unlocked
        and CEL_SUPERIOR in v.card.disciplines
        and PRE_SUPERIOR in v.card.disciplines
        for v in state.players[player].vampires.values()
    )


def _target_title_casts(context: Mapping[str, Any]) -> list[tuple[str, str, int, str]]:
    """ "A vampire who has cast votes or ballots" -- narrowed to `"title:"`-
    sourced casts only (module docstring)."""
    return [cast for cast in context.get("casts", ()) if cast[1].startswith("title:")]


def _provide_scalpel_tongue_basic(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[cel][pre] Choose a vampire who has cast votes or ballots in this
    referendum. The chosen vampire is locked and abstains (this cancels the
    chosen vampire's votes and ballots)."."""
    if context.get("phase") != "mid_cast":
        return []
    player = context["player"]
    if not _controls_basic_vampire(state, player):
        return []
    if not _has_card_in_hand(state, player):
        return []

    options: list[HookOption] = []
    for cast_player, source_id, _votes, _direction in _target_title_casts(context):
        instance_id = source_id.split(":", 1)[1]
        target = state.players[cast_player].vampires.get(instance_id)
        if target is None:
            continue

        def _apply(
            s: GameState,
            cast_player: str = cast_player,
            instance_id: str = instance_id,
            source_id: str = source_id,
        ) -> str:
            play_from_hand(s, player, KRCG_ID)
            vampire = s.players[cast_player].vampires[instance_id]
            vampire.locked = True
            return source_id

        options.append(
            HookOption(
                choice=Choice(
                    f"scalpel_tongue:basic:{source_id}",
                    f"Scalpel Tongue [cel][pre]: lock {target.card.name} and cancel their vote",
                ),
                apply=_apply,
                played_card_type=CARD_TYPE,
            )
        )
    return options


def _provide_scalpel_tongue_superior(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "[CEL][PRE] As above, and the chosen vampire burns 1 blood."."""
    if context.get("phase") != "mid_cast":
        return []
    player = context["player"]
    if not _controls_superior_vampire(state, player):
        return []
    if not _has_card_in_hand(state, player):
        return []

    options: list[HookOption] = []
    for cast_player, source_id, _votes, _direction in _target_title_casts(context):
        instance_id = source_id.split(":", 1)[1]
        target = state.players[cast_player].vampires.get(instance_id)
        if target is None:
            continue

        def _apply(
            s: GameState,
            cast_player: str = cast_player,
            instance_id: str = instance_id,
            source_id: str = source_id,
        ) -> str:
            play_from_hand(s, player, KRCG_ID)
            vampire = s.players[cast_player].vampires[instance_id]
            vampire.locked = True
            vampire.blood = max(0, vampire.blood - BURN_AMOUNT)
            return source_id

        options.append(
            HookOption(
                choice=Choice(
                    f"scalpel_tongue:superior:{source_id}",
                    f"Scalpel Tongue [CEL][PRE]: lock {target.card.name}, cancel their vote, "
                    "and burn 1 blood",
                ),
                apply=_apply,
                played_card_type=CARD_TYPE,
            )
        )
    return options


hooks.register(POLLING_STEP_HOOK, _provide_scalpel_tongue_basic)
hooks.register(POLLING_STEP_HOOK, _provide_scalpel_tongue_superior)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Scalpel Tongue",
        status=Status.IMPLEMENTED,
        hooks=(Hook.POLLING_STEP,),
        source=__name__,
    )
)
