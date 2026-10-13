"""Taste of Vitae (Combat). krcg id 101945.

Card text (verbatim, via the installed `krcg` 5.14+ package's own
`krcg.vtes.VTES["Taste of Vitae"].card_text`, 2026-10-12, matching the raw
snapshot saved to `data/cards/101945.json` byte-for-byte, cross-checked
live against `https://api.krcg.org/card/101945`):
    "Only usable at the end of a round of combat. Not usable by a vampire
    being burned or going to torpor. A vampire can play only one Taste of
    Vitae each round.
    This vampire gains blood equal to the amount of blood lost by the
    opposing vampire to damage this round."

Rulings (verbatim, via krcg; both the installed package and the live API
agree):
    - "Cannot be played against an ally." [PIB 20121028]
    - "Must be played after the presses are handled and can be played if
      the round ends prematurely." [RTR 20001020] [LSJ 20001024]
      [RTR 20030519]
    - "Can be played before or after effects that are played at the end of
      the round or 'when the combat would end' (eg. [AUS] {Telepathic
      Tracking}). Can be played after [CEL] {Psyche!}" [LSJ 20021113]
      [ANK 20191219] [ANK 20180910-1]
    - "Can be played if the opponent was burned." [LSJ 20031201-2]

Card type: Combat (`types == ["Combat"]`). No discipline requirement
(`discipline_requirement == {"type": "Mono", "disciplines": []}`),
`clan_requirement == []`, `path_requirement == []`, `cost is None`,
`burn_option is False`, `trifle is False`. Legal since 1994-09-15; confirmed
on the active 2P allowed list (`data/formats/2p/2026-10-03.json`) and in the
suggested 2P decklist `data/decks/vekn-2p/brujah.json` (2 copies).

No Ⓓ marker, no prey/predator/"other Methuselahs" wording, no political
vote -- a plain Combat card scoped to the current combat's own two
combatants, so OQ-1 (CLAUDE.md SS3) does not apply.

Status: implemented. Previously `blocked` (OQ-29, resolved) for want of (1)
an "End of Round" timing window and (2) a round-scoped "blood lost to
damage" tracker. `rules-engineer`'s fix: `engine/combat.py` gained
`END_OF_ROUND_HOOK`/`_ask_end_of_round`, dispatched once per round via the
engine's standard two-sided, repeatable impulse window
(`hooks.resolve_impulse_window`) on every round-exit path; `engine/
damage.py::apply_damage` gained an optional `round_state` parameter
recording how much blood each vampire actually lost to damage this round,
queryable via `blood_lost_to_damage_this_round(round_state, vampire_id)`
(survives the tracked vampire being burned afterward -- a plain dict entry,
untouched by zone transitions). See `engine/combat.py`'s "End of Round and
round-scoped blood-loss tracking" docstring section for the mechanism.

`END_OF_ROUND_HOOK`'s own context carries `acting_player`/`acting_vampire`/
`blocking_player`/`blocking_vampire` as plain ids (absolute, not
`vampire`/`opponent`-relative like `MANEUVER_HOOK`'s own context) -- this
provider compares `context["player"]` against `acting_player`/
`blocking_player` itself to work out which side it is currently being
offered to, and therefore which vampire is "this vampire" (the one that
would play the card) versus "the opposing vampire" (whose blood-loss record
is queried).

"Only usable at the end of a round of combat.": satisfied structurally --
this provider is only ever offered via `END_OF_ROUND_HOOK`, which exists
nowhere else in the engine.

"Not usable by a vampire being burned or going to torpor.": a target-
legality check on the *playing* vampire's own zone (`zone in {"burned",
"torpor"}` excluded) -- never the opponent's own zone, which is explicitly
unrestricted by the card's own text and ruling ("[c]an be played if the
opponent was burned" [LSJ 20031201-2]); this provider never even reads the
opponent vampire's own `zone`, only its `instance_id`, for exactly this
reason.

"A vampire can play only one Taste of Vitae each round.": a private,
round-scoped per-vampire cap, genuinely separate from the existing
cross-card "(limited)" additional-strike cap (`ADDITIONAL_STRIKE_LIMIT_KEY`,
OQ-19) -- this card's own text never says "(limited)" and has nothing to do
with additional strikes, so its own `_USED_KEY` is a private key inside the
same shared `round_state` dict, never the additional-strike one (same
"private key nested inside the shared dict" convention `dust_up.py`'s own
`CEL_GRANTS_KEY` already uses).

"This vampire gains blood equal to the amount of blood lost by the opposing
vampire to damage this round.": `blood_lost_to_damage_this_round(round_state,
<opposing vampire's instance id>)`, recomputed fresh inside `apply()` (not
captured at offer time), since `END_OF_ROUND_HOOK`'s window is repeatable
and another effect could run between offer and apply. An amount of 0 is not
itself a reason to withhold the option: the card text conditions
playability only on the listed zone/hand/once-per-round gates, not on a
nonzero amount.

"Cannot be played against an ally." [PIB 20121028]: unreachable today, same
reason OQ-7/OQ-10 already note for ally combat generally -- no ally can
currently be a combat participant at all, so "the opposing vampire" in this
card's own text is, today, always actually a vampire.

"Must be played after the presses are handled and can be played if the
round ends prematurely.": exactly `_ask_end_of_round`'s own placement and
"every round-exit path" guarantee (module docstring above) -- no extra
check needed in this module.

"Can be played before or after effects that are played at the end of the
round or 'when the combat would end' (eg. [AUS] {Telepathic Tracking}). Can
be played after [CEL] {Psyche!}": an ordering clarification relative to
Telepathic Tracking (krcg id 101950) and Psyche! (krcg id 101507), neither
implemented in this project's pool -- not separately actionable until at
least one of them is; `END_OF_ROUND_HOOK`'s own repeatable, two-sided
impulse-window shape (any order, any number of plays, by either side)
already accommodates "before or after" generically, with nothing
Taste-of-Vitae-specific needed for it.

"Can be played if the opponent was burned.": the opponent's blood-loss
record (`BLOOD_LOST_TO_DAMAGE_KEY`) is untouched by the opponent's own zone
transition to `"burned"`, and this provider's own zone gate only ever
excludes the *playing* vampire, never the opponent -- so this is already
correctly supported with no extra code.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.combat import END_OF_ROUND_HOOK, ROUND_STATE_CONTEXT_KEY
from vtesbot.engine.damage import add_blood, blood_lost_to_damage_this_round
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 101945
_USED_KEY = "taste_of_vitae_used"
_EXCLUDED_ZONES = ("burned", "torpor")
CARD_TYPE = "Combat"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): matches
this module's own "Card type: Combat" docstring fact above."""


def _provide_taste_of_vitae(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    if player == context["acting_player"]:
        vampire_id = context["acting_vampire"]
        opponent_id = context["blocking_vampire"]
    else:
        vampire_id = context["blocking_vampire"]
        opponent_id = context["acting_vampire"]

    vampire = state.players[player].vampires.get(vampire_id)
    if vampire is None:
        return []
    if vampire.zone in _EXCLUDED_ZONES:
        return []  # "Not usable by a vampire being burned or going to torpor."
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    round_state = context.get(ROUND_STATE_CONTEXT_KEY)
    already_used = round_state is not None and round_state.get(_USED_KEY, {}).get(vampire_id)
    if already_used:
        return []  # "A vampire can play only one Taste of Vitae each round."

    preview_amount = blood_lost_to_damage_this_round(round_state, opponent_id)

    def _apply(s: GameState) -> int:
        play_from_hand(s, player, KRCG_ID)
        if round_state is not None:
            round_state.setdefault(_USED_KEY, {})[vampire_id] = True
        # Recomputed live (not the offer-time preview above): `END_OF_ROUND_
        # HOOK` is a repeatable impulse window, so another effect could in
        # principle run between offer and apply.
        amount = blood_lost_to_damage_this_round(round_state, opponent_id)
        return add_blood(s, vampire, amount)

    return [
        HookOption(
            choice=Choice("taste_of_vitae", f"Taste of Vitae: gain {preview_amount} blood"),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


hooks.register(END_OF_ROUND_HOOK, _provide_taste_of_vitae)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Taste of Vitae",
        status=Status.IMPLEMENTED,
        hooks=(Hook.END_OF_ROUND,),
        source=__name__,
    )
)
