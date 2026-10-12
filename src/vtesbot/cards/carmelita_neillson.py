"""Carmelita Neillson (crypt vampire ability). krcg id 201625.

Printed text (fetched via krcg's live API, `https://api.krcg.org/card/201625`,
2026-10-12; raw snapshot `data/cards/201625.json`, cross-checked against the
installed `krcg` package's own `krcg.vtes.VTES[201625].to_json()["card_text"]`
/ `krcg.vtes.VTES[201625].text`, same wording): "Camarilla: While Carmelita is
ready, you get +1 hand size."

Rulings: none on file (`krcg.vtes.VTES[201625].rulings == []` and the raw API
snapshot's own `"rulings": []`, both checked 2026-10-12).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Toreador, no title
(the live API's own `"title": null`, confirmed -- unlike Marcos Belegrad/
Modius/Atiena/Leumeah, whose own "<Sect> <Title> of <City>:" preamble names an
actual title; Carmelita's own `"Camarilla:"` preamble is a bare sect keyword
with no title at all), group 7, capacity 5, disciplines `["cel", "pre",
"AUS"]`. Legal since 2022-05-17; confirmed on the active 2P allowed list
(`data/formats/2p/2026-10-03.json`).

"Camarilla:" sect-gating -- resolved, not an Open Question: this is the same
bare-sect-colon-preamble shape `engine/cards.py::derive_sect`'s own docstring
names for Ariane ("Anarch: Ariane gets -1 stealth...") and already
implemented, non-title, sect-conditional abilities gate on it for real
(`src/vtesbot/cards/dust_up.py`, `line_brawl.py`, `organized_resistance.py`,
`protection_racket.py`, each checking `vampire.card.sect is Sect.<X>` and
treating `sect is None` as "does not qualify" per `CryptCard`'s own docstring:
"a card gating on sect must treat `None` as 'does not qualify,' never guess a
default sect"). This is a different pattern from Marcos Belegrad's/Modius's/
Atiena's/Leumeah's own "<Sect> <Title> of <City>:" preamble, where the sect
word is fused into the *title name itself* (and those modules correctly left
it unconditional, since the generic `engine/politics.py::TITLE_VOTES` table
already keys purely on the bare title string, with no sect-dependent vote
value -- see `atiena.py`'s own docstring). Carmelita carries no title at all
(`"title": null`, confirmed above), so there is no title machinery for this
preamble to ride on; her "Camarilla:" is read the same way Dust Up's "Requires
an Anarch" and Ariane's "Anarch:" are: a live condition on her own current
`vampire.card.sect`, re-checked every call exactly like her own `zone`/
`locked` are (per `engine/cards.py::CryptCard`'s "plain printed stats, not
behaviour" framing and the hook contract below). In practice, since no card
in this pool implements a sect-change mechanism yet (`protection_racket.py`'s
own "changes sect mid-action" caveat; no such mechanism exists), this check
is always true for a real, `derive_sect`-populated Carmelita instance -- it is
included for consistency with the established convention and to correctly
return no bonus for a synthetic/test vampire whose `sect` was never modeled
(`sect is None`), not because any live game state can presently make it false
for a genuine Carmelita.

"While Carmelita is ready": per `src/vtesbot/cards/registry.py::Hook.
HAND_SIZE_MODIFIER`'s own docstring and `engine/hand.py`'s module docstring,
both naming Carmelita's own `zone`/`locked` as the two fields this
continuously re-evaluated condition reads -- `vampire.zone == "ready"` (in the
ready region, not torpor/uncontrolled/burned) *and* `not vampire.locked`
(unlocked), mirroring the Reaction Card glossary's own distinct "ready,
unlocked minion" phrasing (`data/sources/rulebook/2026-10-09/
8-glossaries.md`), not the looser "ready region" sense `engine/politics.py`'s
generic title-vote gate uses (which is `zone == "ready"` alone, with no
`locked` check, since a locked titled vampire still casts their title vote).

"you get +1 hand size": a passive, mandatory `HAND_SIZE_MODIFIER_HOOK`
contribution (`engine/hand.py::effective_hand_size`, `hooks.sum_modifiers`
contract) for Carmelita's own controller -- +1 while the above conditions
hold, 0 otherwise, re-checked fresh on every call (no caching), exactly as
`cards/registry.py::Hook.HAND_SIZE_MODIFIER`'s own docstring specifies.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.cards import Sect
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 201625
HAND_SIZE_MODIFIER_HOOK = "hand_size_modifier"


def _controlled_ready_carmelita(state: GameState, player: str) -> VampireInPlay | None:
    """Carmelita, controlled by `player`, ready, unlocked, and of the
    Camarilla sect right now -- or `None` if any of that does not hold."""
    for vampire in state.players[player].vampires.values():
        if (
            vampire.card.krcg_id == KRCG_ID
            and vampire.zone == "ready"
            and not vampire.locked
            and vampire.card.sect is Sect.CAMARILLA
        ):
            return vampire
    return None


def _provide_carmelita_hand_size(state: GameState, context: Mapping[str, Any]) -> int:
    player = context["player"]
    return 1 if _controlled_ready_carmelita(state, player) is not None else 0


hooks.register(HAND_SIZE_MODIFIER_HOOK, _provide_carmelita_hand_size)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Carmelita Neillson",
        status=Status.IMPLEMENTED,
        hooks=(Hook.HAND_SIZE_MODIFIER,),
        source=__name__,
    )
)
