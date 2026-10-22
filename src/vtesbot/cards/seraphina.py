"""Seraphina (crypt vampire ability). krcg id 201686.

Printed text (fetched via `krcg.load()` + `msgspec.json.encode()`, project's
`uv run` venv (krcg 5.14), 2026-10-17, matching the raw snapshot
`data/cards/201686.json`): "Independent: Seraphina can add 2 blood or life to
a minion you control as a +1 stealth action, not to exceed starting life."

Rulings: none on file (`rulings == []`, confirmed in the raw snapshot).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Salubri, group 7,
capacity 8, disciplines `("cel", "tha", "AUS", "DOM", "FOR")`. No title.
Legal since 2024-01-31; confirmed on the active 2P allowed list
(`data/formats/2p/2026-10-03.json`) and in the suggested 2P decklist
`data/decks/vekn-2p/salubri.json` (3 copies).

Status: implemented (ENG-041 resolved). Wired against `engine/phases/
minion.py::ACTION_CARD_PLAY_HOOK`, the same shape Sakhar (`cards/sakhar.py`)
uses for an own-printed-ability minion action: one `HookOption` per eligible
"minion you control" target, the specific amount/resource bound at `apply()`
time, the actual add deferred to `resolve()` so a blocked attempt never
touches blood/life (Rulebook §4 Detailed Turn Sequence: "the cost of the
action is paid... only if the action succeeds").

"a minion you control": a vampire or an ally currently in play under this
card's own controller -- `zone in ("ready", "torpor")` for a vampire
(matches `cards/opikun.py`'s own "in play at all" reading; the card text
carries no "ready"/"unlocked" qualifier on the *target*, only on the acting
Seraphina herself, who must already be the ready/unlocked vampire performing
this minion action per the generic `_choose_and_perform_action` gate), and
`zone == "ready"` for an ally -- unlike a contested *crypt* card, a
contested ally is not "in play, usable": the 2P variant's "stays in play,
usable" override is scoped to crypt cards only (ENG-004), so a contested ally follows the
unmodified rulebook rule and sits out of play until its own controller's
next unlock phase restores it (`engine/allies.py::resolve_one_ally_contest`,
`engine/phases/unlock.py::_unlock_own_allies`).

Retainers carry no life/blood field in this engine at all
(`engine/cards.py::CardAttachment` has no such field) and no
retainer-recruiting card is implemented yet, so that branch of "a minion"
is out of scope by construction, not an oversight (module's own prior
`blocked` docstring already noted this).

"add 2 blood or life": which resource applies is determined by the target's
own kind, not a free choice -- a vampire has blood, not life; an ally has
life, not blood (`engine/state.py`'s own field split). One `HookOption` per
target, naming the resource implicitly via the target's type.

"not to exceed starting life": the vampire-target (blood) half needs no
extra cap beyond `engine/damage.py::add_blood`'s existing effective-capacity
clamp (ENG-002) -- a vampire has no separate "starting life" concept, and nothing
in the printed text suggests blood should be capped at anything other than
capacity. The ally-target (life) half is capped at `AllyInPlay.
starting_life` via the new `engine/allies.py::add_life` helper (ENG-041).

A target already at its own cap is never offered (never offer a play that
cannot resolve, `cards/line_brawl.py`'s own precedent; mirrors `cards/
life_in_the_city.py`'s fizzle-avoidance framing, applied at offer time
rather than at resolve time since the cap here is checked against the
*same* value both times -- no other effect in this engine changes a
vampire's effective capacity or an ally's starting life between offer and
resolve).

"+1 stealth action" (bare, no "Ⓓ" marker): undirected, baseline stealth 1 --
same reading `RECRUIT_ALLY_STEALTH`'s/`cards/sakhar.py`'s own docstrings give
for the Rulebook default-action-list's identical bare phrasing, and
consistent with the target being the acting player's own minion (never the
opponent's), matching Enchant Kindred's own `directed=False` "Add 2 blood to
a younger vampire in your uncontrolled region" clause precedent
(`cards/enchant_kindred.py`).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.allies import add_life
from vtesbot.engine.attachments import effective_capacity
from vtesbot.engine.damage import add_blood
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, ActionCardSpec
from vtesbot.engine.state import AllyInPlay, GameState, VampireInPlay

KRCG_ID = 201686
SERAPHINA_STEALTH = 1
"""Verbatim "+1 stealth action" (bare): undirected, baseline 1 (module
docstring)."""
ADD_AMOUNT = 2
"""Verbatim "add 2 blood or life"."""

VAMPIRE_IN_PLAY_ZONES = ("ready", "torpor")
ALLY_IN_PLAY_ZONES = ("ready",)


def _controlled_vampires_in_play(state: GameState, player: str) -> list[VampireInPlay]:
    return [v for v in state.players[player].vampires.values() if v.zone in VAMPIRE_IN_PLAY_ZONES]


def _controlled_allies_in_play(state: GameState, player: str) -> list[AllyInPlay]:
    return [a for a in state.players[player].allies.values() if a.zone in ALLY_IN_PLAY_ZONES]


def _vampire_option(vampire: VampireInPlay) -> HookOption:
    name = vampire.card.name
    label = f"Seraphina: add 2 blood to {name}"

    def _apply(s: GameState) -> ActionCardSpec:
        def resolve(pending: dict[str, Any]) -> None:
            del pending  # no later hook window of its own to feed.
            added = add_blood(s, vampire, ADD_AMOUNT)
            s.log.record_event(f"Seraphina adds {added} blood to {name}")

        return ActionCardSpec(base_stealth=SERAPHINA_STEALTH, directed=False, resolve=resolve)

    return HookOption(choice=Choice(f"seraphina:blood:{vampire.instance_id}", label), apply=_apply)


def _ally_option(ally: AllyInPlay) -> HookOption:
    name = ally.name
    label = f"Seraphina: add 2 life to {name}"

    def _apply(s: GameState) -> ActionCardSpec:
        def resolve(pending: dict[str, Any]) -> None:
            del pending
            # `add_life` needs no `state` (ENG-041): no engine mechanism
            # modifies an ally's own starting life, unlike a vampire's
            # effective capacity (ENG-002).
            added = add_life(ally, ADD_AMOUNT)
            s.log.record_event(f"Seraphina adds {added} life to {name}")

        return ActionCardSpec(base_stealth=SERAPHINA_STEALTH, directed=False, resolve=resolve)

    return HookOption(choice=Choice(f"seraphina:life:{ally.instance_id}", label), apply=_apply)


def _provide_seraphina(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    acting_vampire = state.players[player].vampires.get(context["vampire"])
    if acting_vampire is None or acting_vampire.card.krcg_id != KRCG_ID:
        return []

    options: list[HookOption] = []
    for vampire in _controlled_vampires_in_play(state, player):
        if effective_capacity(state, vampire) - vampire.blood <= 0:
            continue
        options.append(_vampire_option(vampire))
    for ally in _controlled_allies_in_play(state, player):
        if ally.starting_life - ally.life <= 0:
            continue
        options.append(_ally_option(ally))
    return options


hooks.register(ACTION_CARD_PLAY_HOOK, _provide_seraphina)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Seraphina",
        status=Status.IMPLEMENTED,
        hooks=(Hook.ACTION_CARD_PLAY,),
        source=__name__,
    )
)
