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

`HookOption.played_card_type` (ENG-023): this card
prints two types, `["Action Modifier", "Reaction"]` with `combo == True`
(module docstring above), and which half is actually in play depends on
*who* plays it (module docstring's own "Who may play it" section, RUL-010):
the caller plays it as their acting vampire's Action Modifier (the
Rulebook §2 Card Types default for the acting minion), the non-caller
plays it under the ordinary Reaction rule instead. `played_card_type` is
therefore set per-use, not hardcoded: `"Action Modifier"` for the caller's
own use, `"Reaction"` for the non-caller's -- load-bearing for
`hooks.mark_reaction_played`'s `PENDING_REACTION_PLAYED_KEY` tracking
(`cards/perfectionist.py` (krcg 101388)'s "no reaction cards were played"
gate, rules-auditor finding: an earlier draft of this module hardcoded
`"Action Modifier"` for every use, which would have silently hidden the
non-caller's use from that gate).

Status: implemented (ENG-027, resolved --
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

Who may play it (RUL-010, resolved -- user ruling):
asymmetric by role, unlike this module's earlier, uniform "any ready,
unlocked qualifying vampire of either Methuselah" reading.

- The *caller* (the Methuselah whose political action this is):
  `rules-auditor`'s RUL-010 finding applies the Rulebook §2 Card Types
  default ("The acting minion can play [action modifier cards]..." absent
  an "other than the acting minion" override phrase, which this card's text
  does not carry) -- so the caller may only play Scalpel Tongue through
  their own acting vampire specifically, `context["caller_vampire_id"]`,
  never a different ready/unlocked vampire they also control. That specific
  vampire's own `locked` state is irrelevant to this eligibility check: by
  the time the polling step is reached, the acting vampire is *always*
  locked already (Rulebook §4, locked the instant the action was
  announced), so requiring `is_ready_unlocked` here would make the caller's
  own use permanently impossible -- the `is_ready_unlocked` gate below is
  specifically the Reaction-card requirement for the *non-caller* case,
  which does not apply to the acting-minion-by-default Action-Modifier
  case. `_caller_vampire_qualifies_basic`/`_caller_vampire_qualifies_
  superior` implement this: `zone == "ready"` (still in play) plus the
  combo-discipline check, nothing more.
- The *other* Methuselah (not the caller): unaffected by the above default,
  since they are never "the acting minion" for this political action at
  all -- their own use is justified independently by this card's Reaction
  half (`types == ["Action Modifier", "Reaction"]`), governed by the
  ordinary Reaction rule instead: any ready, *unlocked* qualifying vampire
  they control, checked by the pre-existing `_controls_basic_vampire`/
  `_controls_superior_vampire` (`is_ready_unlocked` gate, `telepathic_
  counter.py`'s own convention -- `rules-auditor` finding: an earlier draft
  of this module checked only `zone == "ready"`, which would have let a
  *locked* vampire play this card's Reaction half, contra the glossary's "a
  ready unlocked minion can play a reaction card").

Either way, the vampire that *plays* this card is otherwise irrelevant to
its effect (unlike Voter Captivation's "this vampire" clause) -- only its
existence/discipline/readiness is checked, no specific one is chosen or
recorded; the targeting logic below (`_target_title_casts`) is identical
for both roles.

Target may already be locked (user ruling): "Choose a vampire who has cast
votes or ballots" places no requirement that the target currently be
*unlocked* -- `VampireInPlay.locked` is irrelevant to voting (`engine/
politics.py`'s own convention, cited in `voter_captivation.py` too), so a
vampire that voted while already locked (e.g. it had already performed its
own action earlier this turn, locking it, before casting a title vote) is a
perfectly legal target. `apply`'s own `vampire.locked = True` is simply
idempotent in that case -- the vampire was locked, is chosen, and remains
locked, with no toggle, no double-lock bookkeeping, and no special-case
needed in code.

"The chosen vampire is locked and abstains (this cancels the chosen
vampire's votes and ballots)": two separate effects, per ENG-027's own
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
(RUL-005's own note, same "unreachable today, not a
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
CALLER_CARD_TYPE = "Action Modifier"
NON_CALLER_CARD_TYPE = "Reaction"
"""`HookOption.played_card_type` (ENG-023): which of
this card's two printed types (module docstring) applies depends on who
plays it -- see `_played_card_type` below."""


def _played_card_type(player: str, context: Mapping[str, Any]) -> str:
    """The caller plays this card as their acting vampire's Action
    Modifier; the non-caller plays it under the ordinary Reaction rule
    (module docstring's "Who may play it", RUL-010)."""
    return CALLER_CARD_TYPE if player == context["caller"] else NON_CALLER_CARD_TYPE


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _controls_basic_vampire(state: GameState, player: str) -> bool:
    """ "[cel][pre]" (module docstring, `combo == True`): at least one ready,
    unlocked vampire (Rulebook §2 Card Types glossary: "A ready unlocked
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


def _caller_may_play_basic(state: GameState, context: Mapping[str, Any]) -> bool:
    """RUL-010 (resolved): the caller's own use is
    the Action-Modifier default ("the acting minion"), not the Reaction
    rule -- `zone == "ready"` only, `locked` irrelevant (module docstring's
    "Who may play it")."""
    vampire = state.players[context["caller"]].vampires.get(context["caller_vampire_id"])
    return (
        vampire is not None
        and vampire.zone == "ready"
        and (CEL_BASIC in vampire.card.disciplines or CEL_SUPERIOR in vampire.card.disciplines)
        and (PRE_BASIC in vampire.card.disciplines or PRE_SUPERIOR in vampire.card.disciplines)
    )


def _caller_may_play_superior(state: GameState, context: Mapping[str, Any]) -> bool:
    """Superior-level counterpart of `_caller_may_play_basic`."""
    vampire = state.players[context["caller"]].vampires.get(context["caller_vampire_id"])
    return (
        vampire is not None
        and vampire.zone == "ready"
        and CEL_SUPERIOR in vampire.card.disciplines
        and PRE_SUPERIOR in vampire.card.disciplines
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
    if player == context["caller"]:
        may_play = _caller_may_play_basic(state, context)
    else:
        may_play = _controls_basic_vampire(state, player)
    if not may_play:
        return []
    if not _has_card_in_hand(state, player):
        return []

    played_card_type = _played_card_type(player, context)
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
                played_card_type=played_card_type,
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
    if player == context["caller"]:
        may_play = _caller_may_play_superior(state, context)
    else:
        may_play = _controls_superior_vampire(state, player)
    if not may_play:
        return []
    if not _has_card_in_hand(state, player):
        return []

    played_card_type = _played_card_type(player, context)
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
                played_card_type=played_card_type,
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
