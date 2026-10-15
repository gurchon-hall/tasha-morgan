"""Queen Anne (crypt vampire ability). krcg id 201647.

Printed text (verbatim, via the installed `krcg` package, `from krcg import
vtes; vtes.VTES.load(); vtes.VTES[201647].card_text`, re-verified live
2026-10-15): "Camarilla Prince of London: During the polling step of a
referendum called by Anne, she can burn 1 blood to force a younger
Camarilla vampire to abstain. After she diablerizes a vampire, she can
unlock. +1 bleed." Clan Ventrue, title Prince, group 6, capacity 10,
disciplines `["aus", "obf", "DOM", "FOR", "PRE"]`.

No ruling on file for this card (`vtes.VTES[201647].rulings == []`,
re-verified live 2026-10-15; same result as the stub's own earlier,
pre-live-verification note).

Three clauses:

1. "During the polling step of a referendum called by Anne, she can burn 1
   blood to force a younger Camarilla vampire to abstain." Built against
   the generic `POLLING_STEP_HOOK`/`pending["forced_abstain"]` mechanism
   (OQ-6, `engine/politics.py::_collect_vote_sources`), proven generically
   by `tests/rules/test_politics.py::
   test_a_forced_abstain_source_is_excluded_from_casting_end_to_end` --
   that mechanism is this clause's whole blocker-removal; no engine gap
   remains.

   "Younger": Rulebook §2 Card Types, verbatim -- "A vampire with a larger
   capacity than another is said to be older, and one with a smaller
   capacity is younger" (`data/sources/rulebook/2026-10-09/
   2-card-types.md:30`) -- a plain, *printed* `CryptCard.capacity`
   comparison (not `effective_capacity`: this is about a vampire's
   identity/age, the same "capacity, not effective_capacity" reading
   `grooming_the_protege.py` already applies to an identically-worded
   "younger" clause), so the earlier stub's belief that a missing
   `generation` field blocked this clause was simply wrong -- the
   rulebook never ties "younger" to generation at all. Strictly less
   than Anne's own printed capacity (10): same capacity is neither older
   nor younger per that same sentence, so a same-capacity Camarilla
   vampire does not qualify (settled directly by the rulebook wording,
   not a guess).

   "A referendum called by Anne" (not "any referendum", unlike Alexa
   Draper's/Modius's own unqualified wording): gated on
   `context["caller_vampire_id"]` resolving, within the *offered*
   player's own vampires, to a vampire that is Anne herself
   (`krcg_id == KRCG_ID`) -- mirrors `diana_iadanza.py`'s identical
   "During a referendum she calls" gate
   (`test_not_usable_if_the_referendum_was_not_called_by_diana_herself`).
   Since the opposing Methuselah never controls the instance id named by
   `caller_vampire_id`, this gate also naturally restricts the whole
   ability to Anne's own controller -- consistent with every other
   printed "<name> can ..." vampire ability in this pool (Modius, Alexa
   Draper, Lucinde).

   Only effective during the pre-cast window (`phase == "before_cast"`):
   `pending["forced_abstain"]` is consumed once, by `_collect_vote_sources`,
   immediately after that window closes and before `_cast_votes` ever
   starts (`engine/politics.py::resolve_referendum`). Adding to it during
   the later mid-cast window would be a silent no-op (the source list is
   already built by then), so this module never offers the option while
   `context["phase"] == "mid_cast"` (CLAUDE.md "never offer a play that
   cannot resolve", `line_brawl.py`'s own convention).

   Target pool: "a younger Camarilla vampire" carries no "yours"/
   "opponent's" qualifier, so both Methuselahs' vampires are eligible
   (judgment call, matching the instruction that undirected/unqualified
   wording in a 2P duel reaches either side unless the text says
   otherwise) -- `zone == "ready"` (the engine's own vote-source-eligible
   zone; a torpid vampire already must abstain, Rulebook §4 line 1074,
   so forcing an abstain on one would be a no-op), `card.sect is
   Sect.CAMARILLA` (`sect is None` does not qualify, same convention as
   `carmelita_neillson.py`), `card.capacity < 10`, and `card.title` names
   an actual vote source (`politics.TITLE_VOTES`) -- a Camarilla vampire
   with no title has no vote to force into abstention either, so
   offering it would be equally inert (the same "never offer a no-op"
   reasoning as above, not a narrowing of the card text's own "vampire"
   wording: every excluded candidate would have had literally zero
   observable effect).

   Cost/gate on Anne herself: 1 blood burned, never offered with less
   than that; `is_ready_unlocked` (ready *and* unlocked) -- unlike Alexa
   Draper, no on-file ruling grants this ability a "usable while locked"
   exception, so the ordinary default applies here instead of copying
   that permission over without a reason.

   Rulebook §3 "Wording templates" > "During X, do Y", verbatim: "only
   one Y can be done per X with this card" (`data/sources/rulebook/
   2026-10-09/3-playing-the-game.md` lines 86-91) -- caps this ability at
   once per referendum, tracked via `context["pending"]` the same way
   `diana_iadanza.py`/`alexa_draper.py` track their own identical cap.

2. "After she diablerizes a vampire, she can unlock." Built against
   `engine/diablerie.py::DIABLERIE_HOOK`, the primitive that module's own
   docstring names this card as its intended first consumer; mirrors
   `tests/rules/test_diablerie.py::
   test_diablerie_hook_fires_while_the_diablerist_is_still_in_play_before_
   the_blood_hunt`'s own fake provider shape, including its "stop
   offering once already unlocked" guard (`resolve_impulse_window` keeps
   re-offering within the same window until both sides pass in a row;
   without the guard an unlocked-but-still-reachable Anne would be
   offered a no-op option every remaining turn of that window). Scoped to
   Anne herself being the diablerist (`krcg_id == KRCG_ID` on the vampire
   named by `context["diablerist"]`), not merely present in play: the
   victim's controller's own lookup of that same instance id naturally
   misses (instance ids are unique across both players), so this never
   fires for anyone but the diablerist's own controller.

3. "+1 bleed": flat, unconditional, mirrors `diana_iadanza.py`'s/
   `lucinde_alastor.py`'s identically-shaped trailing clause, gated only
   on Anne being the acting vampire for the bleed.

Status: implemented.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.cards import Sect
from vtesbot.engine.decision import Choice
from vtesbot.engine.diablerie import DIABLERIE_HOOK
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.politics import POLLING_STEP_HOOK, TITLE_VOTES
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 201647
BLOOD_COST = 1
"""Printed "burn 1 blood" (clause 1)."""
BLEED_AMOUNT_FIXED_MODIFIER_HOOK = "bleed_amount_fixed_modifier"
PENDING_USED_KEY = "queen_anne_forced_abstain_used"
"""Once-per-referendum cap (module docstring's Rulebook "During X, do Y"
citation), tracked in `context["pending"]` -- naturally scoped to one
`resolve_referendum` call, since `pending` is a fresh dict per call."""


def _controlled_ready_unlocked_anne(
    state: GameState, player: str, instance_id: str | None
) -> VampireInPlay | None:
    """Anne, controlled by `player`, matching `instance_id`
    (`context["caller_vampire_id"]`), `is_ready_unlocked` (module
    docstring: no ruling licenses use while locked, unlike Alexa Draper).
    """
    if instance_id is None:
        return None
    vampire = state.players[player].vampires.get(instance_id)
    if vampire is None or vampire.card.krcg_id != KRCG_ID:
        return None
    if not vampire.is_ready_unlocked:
        return None
    return vampire


def _eligible_forced_abstain_targets(
    state: GameState, anne: VampireInPlay
) -> list[tuple[str, VampireInPlay]]:
    """ "A younger Camarilla vampire" (module docstring): either
    Methuselah's `zone == "ready"`, `Sect.CAMARILLA`, strictly lower
    printed capacity than Anne's own, titled with an actual vote source
    (`politics.TITLE_VOTES`) -- never offering a target whose forced
    abstention would be a no-op."""
    targets: list[tuple[str, VampireInPlay]] = []
    for player_id, player_state in state.players.items():
        for vampire in player_state.vampires.values():
            if vampire.zone != "ready":
                continue
            if vampire.card.sect is not Sect.CAMARILLA:
                continue
            if vampire.card.capacity >= anne.card.capacity:
                continue
            if vampire.card.title not in TITLE_VOTES:
                continue
            targets.append((player_id, vampire))
    return targets


def _provide_queen_anne_forced_abstain(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "During the polling step of a referendum called by Anne, she can
    burn 1 blood to force a younger Camarilla vampire to abstain." See
    module docstring for the `before_cast`-only timing, the "called by
    Anne" gate, the target pool, and the once-per-referendum cap."""
    if context.get("phase") != "before_cast":
        return []
    player = context["player"]
    anne = _controlled_ready_unlocked_anne(state, player, context.get("caller_vampire_id"))
    if anne is None:
        return []
    if anne.blood < BLOOD_COST:
        return []
    pending = context.get("pending")
    if pending is None or pending.get(PENDING_USED_KEY, False):
        return []

    options: list[HookOption] = []
    for _target_player, target in _eligible_forced_abstain_targets(state, anne):
        source_id = f"title:{target.instance_id}"

        def _apply(s: GameState, anne: VampireInPlay = anne, source_id: str = source_id) -> None:
            anne.blood -= BLOOD_COST
            pending["forced_abstain"].add(source_id)
            pending[PENDING_USED_KEY] = True

        options.append(
            HookOption(
                choice=Choice(
                    f"queen_anne_forced_abstain:{target.instance_id}",
                    f"Queen Anne: burn 1 blood to force {target.card.name} to abstain",
                ),
                apply=_apply,
                # `played_card_type` stays at its default `None`: this
                # option is Anne's own printed ability being activated,
                # not a card being played.
            )
        )
    return options


def _provide_queen_anne_diablerie_unlock(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "After she diablerizes a vampire, she can unlock." See module
    docstring for the "Anne herself is the diablerist" scoping and the
    already-unlocked no-op guard."""
    diablerist = state.players[context["player"]].vampires.get(context["diablerist"])
    if diablerist is None or diablerist.card.krcg_id != KRCG_ID:
        return []
    if not diablerist.locked:
        return []  # already unlocked: nothing to offer (stops the re-offer loop).

    def _apply(s: GameState, diablerist: VampireInPlay = diablerist) -> None:
        diablerist.locked = False

    return [
        HookOption(
            choice=Choice("queen_anne_diablerie_unlock", "Queen Anne: unlock"),
            apply=_apply,
        )
    ]


def _provide_queen_anne_bleed(state: GameState, context: Mapping[str, Any]) -> int:
    """ "+1 bleed" -- mirrors `diana_iadanza.py`'s/`lucinde_alastor.py`'s
    identical trailing clause."""
    player = context["player"]
    vampire = state.players[player].vampires.get(context["vampire"])
    if vampire is None or vampire.card.krcg_id != KRCG_ID:
        return 0
    return 1


hooks.register(POLLING_STEP_HOOK, _provide_queen_anne_forced_abstain)
hooks.register(DIABLERIE_HOOK, _provide_queen_anne_diablerie_unlock)
hooks.register(BLEED_AMOUNT_FIXED_MODIFIER_HOOK, _provide_queen_anne_bleed)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Queen Anne",
        status=Status.IMPLEMENTED,
        hooks=(Hook.POLLING_STEP, Hook.DIABLERIE, Hook.BLEED_AMOUNT_FIXED_MODIFIER),
        source=__name__,
    )
)
