"""Diablerie resolution + the automatic Blood Hunt referendum (Rulebook §4
Torpor > "Diablerie"/"The Blood Hunt", lines 1076-1118 of
`data/sources/rulebook/2026-10-09/4-detailed-turn-sequence.md`, re-fetched
live 2026-10-15 at the same URL with no diff). The triggering "Diablerise a
Vampire in Torpor" default minion action (same file, lines 380-404) lives
in `engine/phases/minion.py::ACTION_DIABLERIE`/`_perform_diablerise`;
`resolve_diablerie` below only runs once that action is confirmed
unblocked -- the blocked branch ("the acting vampire and the blocking
minion enter combat as normal") is already the generic
`engine/action.py::perform_minion_action` block path, same as every other
default/action-card minion action (`cards/line_brawl.py`'s own `[pot]`
clause).

Deliberately out of scope this pass (flagged, not missed): the rulebook's
own ADVANCED RULES steps for Diablerie --

- **4.** If the victim was older (higher capacity) than the diablerist,
  fetching a master Discipline card from library/ash heap/hand. Needed by
  Queen Anne's own clause 1 ("younger" comparison, plain `CryptCard.
  capacity`, no engine gap) but her clause 2 ("after she diablerizes a
  vampire, she can unlock") only needs this module's basic-rules steps
  1-3 plus `DIABLERIE_HOOK` below.
- **5.** Red List trophies: this project has no "Red List" data at all.

Only the basic-rules steps 1-3 are built here."""

from typing import TYPE_CHECKING

from . import hooks
from .damage import add_blood, burn_vampire
from .decision import Choice, Decision
from .hooks import Hook
from .politics import resolve_referendum

if TYPE_CHECKING:
    from .cards import CardAttachment
    from .state import GameState, VampireInPlay

DIABLERIE_HOOK = Hook.DIABLERIE
"""Two-sided impulse window (`resolve_impulse_window`, acting Methuselah
first) after diablerie steps 1-3, before the Blood Hunt referendum; options
are optional effects, not forced ones (e.g. Queen Anne's unlock)."""


def _move_attachment_to_diablerist(
    victim: VampireInPlay,
    attachment: CardAttachment,
    diablerist: VampireInPlay,
    diablerist_player: str,
) -> None:
    """Diablerie step 2's "take" branch: re-host `attachment` onto the
    diablerist. Deliberately not `engine/attachments.py::
    transfer_attachment_control`: that helper's own "controller unchanged
    -> host must be unchanged, else `ValueError`" guard is a Disputed
    Territory-specific rule about *locations* ([LSJ 19971002], ENG-025), not
    diablerie -- diablerie legitimately moves an attachment onto a
    *different* vampire even when the diablerist already controls it
    (diablerizing one's own torpid vampire), which that guard would
    otherwise wrongly reject. No currently-implemented equipment card
    (only `cards/weighted_walking_stick.py`) ever gives an attachment a
    `controller` other than its host's own controller, so the "Fame can be
    controlled by someone other than its host" case `CardAttachment`'s own
    docstring flags is not reachable through this path today; this helper
    does not special-case it either way."""
    victim.attachments.remove(attachment)
    diablerist.attachments.append(attachment)
    attachment.controller = diablerist_player


def resolve_diablerie(
    state: GameState,
    diablerist_player: str,
    diablerist: VampireInPlay,
    victim_player: str,
    victim: VampireInPlay,
) -> None:
    """Resolve an already-successful diablerie (Rulebook §4 "Diablerie",
    basic rules steps 1-3 only -- module docstring), then
    `DIABLERIE_HOOK`, then the automatic Blood Hunt referendum. The
    caller is responsible for everything up to "the action is successful"
    (announce/block); this function assumes that has already happened.

    Step ordering for `DIABLERIE_HOOK` vs. the Blood Hunt: the rulebook's
    "Diablerie" section resolves steps 1-3 to completion as one unit
    ("Diablerie is resolved as follows: **1.** ... **2.** ... **3.** The
    victim is burned ..."), and only afterwards does a textually and
    procedurally separate "#### The Blood Hunt" subsection describe the
    automatic referendum ("When a vampire commits diablerie, a referendum
    is automatically and immediately conducted ..."). A reaction tied to
    "after [the diablerist] diablerizes a vampire" (Queen Anne) therefore
    fires before that later subsection, not interleaved with it -- also
    the only ordering under which the diablerist is guaranteed to still
    be in play to receive the option (the Blood Hunt may burn her
    immediately afterward)."""
    # CLAUDE.md §3: in 2P the sole opponent is always both prey and
    # predator -- `opponent` below is "the other Methuselah in this game"
    # for the `DIABLERIE_HOOK` impulse window and the Blood Hunt
    # referendum, deliberately *not* `victim_player`: an undirected
    # diablerie of one's own torpid vampire has `victim_player ==
    # diablerist_player`, which would collapse both sides of those
    # two-player windows onto the same Methuselah.
    opponent = state.other_player(diablerist_player)
    state.log.record_event(
        f"{diablerist.card.name} ({diablerist.instance_id}) diablerises "
        f"{victim.card.name} ({victim.instance_id})"
    )

    # Step 1: "All blood on the victim is moved to the diablerist. Blood
    # in excess of their capacity drains off as normal." `add_blood`
    # already floors the gain at the diablerist's remaining effective
    # capacity (engine/damage.py) -- the excess simply never arrives,
    # which *is* "drains off as normal" for this engine's blood model
    # (blood off the board is never tracked anywhere else).
    add_blood(state, diablerist, victim.blood)
    victim.blood = 0

    # Step 2: "The diablerist may take any equipment on the victim." --
    # a per-item Decision (CLAUDE.md rule 3: never an all-or-nothing
    # grant), offered only for `is_equipment` attachments (Rulebook §2
    # Card Types "Equipment cards"; `CardAttachment.is_equipment`'s own
    # docstring) -- a discipline/archetype master-card attachment (e.g.
    # Celerity) or a Unique master card attached to the victim (e.g.
    # Fame) is never equipment and is never offered here; it falls
    # through to step 3's burn below, same as declined equipment.
    for attachment in list(victim.attachments):
        if not attachment.is_equipment:
            continue
        choices = (
            Choice("take", f"Take {attachment.name} from the victim"),
            Choice("leave", f"Leave {attachment.name} (it burns with the victim)"),
        )
        decision = Decision(
            player=diablerist_player,
            kind="diablerie_take_equipment",
            choices=choices,
            context={
                "attachment": attachment.instance_id,
                "diablerist": diablerist.instance_id,
                "victim": victim.instance_id,
            },
        )
        if state.ask(decision).value == "take":
            _move_attachment_to_diablerist(victim, attachment, diablerist, diablerist_player)

    # Step 3: "The victim is burned. Any cards and counters on them are
    # also burned." Everything still in `victim.attachments` at this
    # point (declined equipment, plus every non-equipment attachment,
    # never offered above) is burned, mirroring `engine/attachments.py`'s
    # own existing "zone = 'burned'" convention
    # (`detect_contest_on_attach`/`resolve_one_attachment_contest`) rather
    # than inventing a new one. "Counters" beyond blood (already fully
    # consumed by step 1): no other per-vampire counter type exists
    # anywhere in this project's implemented card pool today (checked:
    # `VampireInPlay` carries no generic counter field besides `blood`) --
    # vacuously nothing else to burn, correctly modeled either way
    # (`cards/slam.py`'s own phrasing for an analogous "nothing reachable
    # today" case).
    for attachment in victim.attachments:
        attachment.zone = "burned"
    burn_vampire(state, victim_player, victim)

    # "After she diablerizes a vampire, she can unlock." (Queen Anne,
    # krcg 201647) and any equivalent future card -- see this function's
    # own docstring for why this fires before the Blood Hunt below.
    hooks.resolve_impulse_window(
        state,
        DIABLERIE_HOOK,
        diablerist_player,
        opponent,
        context={
            "diablerist": diablerist.instance_id,
            "victim": victim.instance_id,
            "victim_player": victim_player,
        },
    )
    if state.game_over:
        return

    # The Blood Hunt (lines 1105-1118): "a referendum is automatically and
    # immediately conducted ... This referendum is not an action, so it
    # cannot be blocked, and action modifiers and reaction cards cannot
    # be played. Otherwise, this referendum is handled just like any
    # other." Calling `resolve_referendum` directly, bypassing
    # `political_action()`'s own announce/block machinery entirely,
    # already gives "cannot be blocked" and "no action modifiers" for
    # free; cards usable "during the polling step" of a referendum still
    # apply normally through `resolve_referendum`'s own pre-cast/mid-cast
    # `POLLING_STEP_HOOK` windows ("handled just like any other").
    #
    # `include_caller_card_vote=False` fixes a real vote-source bug
    # (`engine/politics.py::resolve_referendum`'s own docstring): nobody
    # cast a political action card to trigger this referendum, so neither
    # side may claim the "+1 vote for casting a political action card"
    # source; both sides keep the generic, symmetric "burn a political
    # action card from hand for a vote" option instead (Rulebook §4
    # Politics > Gaining Votes > Political Action Cards: "Each Methuselah
    # may gain 1 vote by using a political action card ... Each
    # Methuselah can gain no more than 1 vote from political action
    # cards" -- a per-Methuselah cap, not a caller-only right).
    #
    # `caller_player`/`caller_vampire` = the diablerist's own side (and
    # `other_player` = `opponent`, not `victim_player` -- see this
    # function's own top-of-body comment): the referendum's own subject
    # is "whether to call a blood hunt on the diablerist" (Rulebook), so
    # she is the natural `caller_vampire` for hook-context bookkeeping
    # (`REFERENDUM_TALLIED_HOOK`/`VOTE_AGAINST_POOL_COST_HOOK`). This
    # choice is provably mechanics-neutral for actual voting rights: with
    # `include_caller_card_vote=False`, `_collect_vote_sources` grants
    # both sides fully symmetric vote sources (titles, Edge, and the
    # from-hand burn) regardless of which side is nominally "caller" --
    # see `engine/politics.py::_collect_vote_sources`'s own docstring.
    votes_for, votes_against, _casts = resolve_referendum(
        state,
        diablerist_player,
        opponent,
        diablerist,
        include_caller_card_vote=False,
    )
    if state.game_over:
        return
    if votes_for > votes_against:
        state.log.record_event(
            f"Blood hunt called on {diablerist.card.name} ({diablerist.instance_id})"
        )
        burn_vampire(state, diablerist_player, diablerist)
