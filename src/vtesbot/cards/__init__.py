"""Card effect modules and the implementation registry (CLAUDE.md SS5/SS6).

Importing this package runs every known card module's top-level
`register(CardRegistration(...))` call (`src/vtesbot/cards/registry.py`),
populating the registry and (for any card whose module wires one)
`engine/hooks.py` before anything queries either. CLAUDE.md SS6: "A card is
implemented only when: effect code + test(s) ... + registry entry + listed
in the active 2P list" -- modules imported here may be `status=blocked`
(an unresolved ruling or a missing engine mechanism is documented in the
module itself and in `docs/OPEN_QUESTIONS.md`) as well as `implemented`.

Most of the active 2P pool (`data/decks/vekn-2p/*.json`) has *no* module
listed here yet -- that is the normal, unremarkable state for a card nobody
has implemented or found a reason to block yet (see the rules-engineer
milestone-3 scaffolding report for the full classification), not an error.
"""

from . import (
    alexa_draper,
    bonding,
    celerity,
    diana_iadanza,
    disputed_territory,
    dust_up,
    enchant_kindred,
    fiorenza_savona,
    forty_seventh_street_royals,
    grooming_the_protege,
    kine_resources_contested,
    life_in_the_city,
    marcos_belegrad,
    modius,
    oxford_university_england,
    parity_shift,
    perfect_paragon,
    queen_anne,
    scalpel_tongue,
    side_strike,
    telepathic_counter,
    threats,
    voter_captivation,
)

__all__: list[str] = []  # import-for-side-effect only; nothing is re-exported.

_LOADED_MODULES = (
    alexa_draper,
    bonding,
    celerity,
    diana_iadanza,
    disputed_territory,
    dust_up,
    enchant_kindred,
    fiorenza_savona,
    forty_seventh_street_royals,
    grooming_the_protege,
    kine_resources_contested,
    life_in_the_city,
    marcos_belegrad,
    modius,
    oxford_university_england,
    parity_shift,
    perfect_paragon,
    queen_anne,
    scalpel_tongue,
    side_strike,
    telepathic_counter,
    threats,
    voter_captivation,
)
