"""Opikun (crypt vampire ability). krcg id 201680.

Printed text (fetched via `krcg.load()` + `msgspec.json.encode()`, project's
`uv run` venv (krcg 5.14), 2026-10-17, matching the raw snapshot
`data/cards/201680.json`): "Independent: Once each combat involving a
vampire you control, Opikun can burn 1 blood to prevent up to 2
non-aggravated damage to that vampire from the opposing minion's strike."

Rulings (verbatim, via krcg):
    - "The ability can be used when in torpor." [LSJ 20011022]
    - "Cannot be used to prevent aggravated damage, even if the minion
      treats them as normal damage (eg. Skin of Night)."
      [LSJ 20040812-2] [PIB 20130327]

Card type: crypt vampire (`types == ["Vampire"]`). Clan Salubri, group 7,
capacity 5, disciplines `("aus", "dom", "FOR")`. No title. Legal since
2024-01-31; confirmed on the active 2P allowed list (`data/formats/2p/
2026-10-03.json`) and in the suggested 2P decklist `data/decks/vekn-2p/
salubri.json` (2 copies).

Wired against `engine/damage.py::DAMAGE_PREVENTION_HOOK`, offered to the
damaged vampire's own controller (`apply_damage`'s own `player` argument) --
exactly "a vampire you control" already, since Opikun's own controller is
looked up as the *same* player. 2P combat is always strictly one vampire per
side (RUL-001), so "from the opposing
minion's strike" needs no separate attacker check beyond "this damage comes
from an active combat's own strike resolution at all": `context[
COMBAT_STATE_CONTEXT_KEY]` is only non-`None` when `apply_damage` is called
from inside `engine/combat.py::run_combat`'s own strike-resolution call
sites (its own docstring); a non-combat damage source (e.g. Pulled Fangs' own
attachment-damage trigger) passes `combat_state=None` and is correctly never
offered here.

"Once each combat": `combat_state` is the shared, combat-scoped (not
round-scoped) scratch dict `run_combat` creates once per combat (same
primitive Saku Pihlajamäki's own once-per-combat maneuver grant already
uses, `cards/saku_pihlajamaki.py`) -- a fresh `set[str]` of already-used
Opikun instance ids, so two separate copies of Opikun each get their own
independent once-per-combat use (mirrors RUL-012's "two independent sources"
reasoning), and the same copy cannot be reoffered in a later round of the
same combat.

"Opikun can burn 1 blood": the cost is paid from Opikun's own blood pool (no
"from this vampire" qualifier ties it to the damaged vampire; the ordinary
reading is that the named ability-user pays their own cost, Rulebook §2
"Costs are paid from own resources only") -- gated on `opikun.blood >= 1`;
not offered below that. [LSJ 20011022] settles that this holds even while
Opikun herself is in torpor, so the gate below checks `zone in ("ready",
"torpor")`, never `is_ready_unlocked`.

"prevent up to 2 non-aggravated damage": mirrors `cards/soak.py`'s own
`_prevent_non_aggravated` shape -- reduces `damage_box["normal"]` by
`min(2, damage_box["normal"])`, never touching `"aggravated"`
[LSJ 20040812-2] [PIB 20130327], and gated on `damage_box["normal"] > 0`
(never offer a no-op, same convention Soak's own docstring cites for an
identical "cannot be used if there is no damage to prevent" shape). "Up to"
is exactly this clamp: no separate 1-vs-2 choice is needed. The
"even if the minion treats them as normal damage (eg. Skin of Night)" half of
the second ruling has no engine mechanism to convert aggravated damage into
the `"normal"` bucket at all in this codebase yet (no such card is
implemented), so this module cannot yet be exercised against that specific
edge case -- latent, not a blocker, matching `cards/precognition.py`'s own
docstring precedent for an identically-shaped, currently-unreachable corner
case.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.damage import COMBAT_STATE_CONTEXT_KEY, DAMAGE_PREVENTION_HOOK
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 201680
BLOOD_COST = 1
"""Printed "burn 1 blood"."""
PREVENT_AMOUNT = 2
"""Printed "up to 2 non-aggravated damage"."""
IN_PLAY_ZONES = ("ready", "torpor")
"""[LSJ 20011022]: usable while in torpor too -- in play at all, never
`is_ready_unlocked` (mirrors `cards/lucinde_alastor.py`'s own identical
torpor-usable gate)."""
USED_KEY = "opikun_used_this_combat"
"""Key inside `combat_state` (module docstring): a `set[str]` of Opikun
instance ids already used this combat, mirroring `cards/
saku_pihlajamaki.py`'s own once-per-combat cap shape."""


def _controlled_opikun_instances(state: GameState, player: str) -> list[VampireInPlay]:
    return [
        v
        for v in state.players[player].vampires.values()
        if v.card.krcg_id == KRCG_ID and v.zone in IN_PLAY_ZONES
    ]


def _prevent_non_aggravated(damage_box: dict[str, int], amount: int) -> None:
    """Mirrors `cards/soak.py`'s own helper: reduces `damage_box["normal"]`
    by `min(amount, normal)`, never touches `"aggravated"`."""
    normal = damage_box.get("normal", 0)
    damage_box["normal"] = normal - min(amount, normal)


def _provide_opikun(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    combat_state = context.get(COMBAT_STATE_CONTEXT_KEY)
    if combat_state is None:
        return []  # not strike damage from an active combat (module docstring).
    damage_box = context["damage"]
    if damage_box.get("normal", 0) <= 0:
        return []  # "Cannot be used if there is no damage to prevent" convention.

    damaged_vampire = state.players[player].vampires.get(context["vampire"])
    damaged_name = damaged_vampire.card.name if damaged_vampire is not None else "that vampire"

    used = combat_state.setdefault(USED_KEY, set())
    options: list[HookOption] = []
    for opikun in _controlled_opikun_instances(state, player):
        if opikun.instance_id in used:
            continue
        if opikun.blood < BLOOD_COST:
            continue

        def _apply(s: GameState, opikun: VampireInPlay = opikun) -> None:
            del s
            opikun.blood -= BLOOD_COST
            used.add(opikun.instance_id)
            _prevent_non_aggravated(damage_box, PREVENT_AMOUNT)

        options.append(
            HookOption(
                choice=Choice(
                    f"opikun:{opikun.instance_id}",
                    f"Opikun: burn 1 blood to prevent up to 2 non-aggravated damage "
                    f"to {damaged_name}",
                ),
                apply=_apply,
            )
        )
    return options


hooks.register(DAMAGE_PREVENTION_HOOK, _provide_opikun)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Opikun",
        status=Status.IMPLEMENTED,
        hooks=(Hook.DAMAGE_PREVENTION,),
        source=__name__,
    )
)
