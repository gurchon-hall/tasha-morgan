"""`LibraryCard.discipline_requirement` (`engine/cards.py`): krcg's own
`Card.discipline_requirement` field, mirrored verbatim (type Mono/Choice/
Combo, lowercase trigrams, level-agnostic), plus the `requires_discipline`
helper built for Alexa Draper's eventual "discard a card requiring Dominate"
provider (`cards/alexa_draper.py`, still `blocked` as of this pass).

Shapes confirmed live via the installed krcg package, 2026-10-15 (see
`tests/decks/test_loader.py::test_library_card_discipline_requirement_
round_trips_from_krcg` for the full deck-construction round trip from real
cards); this file covers the plain dataclass/helper semantics in isolation.
"""

from vtesbot.engine.cards import (
    DisciplineRequirement,
    DisciplineRequirementType,
    LibraryCard,
    requires_discipline,
)


class TestDisciplineRequirementDefault:
    def test_library_card_defaults_to_no_requirement(self):
        card = LibraryCard(krcg_id=1, name="Test Card", card_type="master")
        assert card.discipline_requirement == DisciplineRequirement(
            type=DisciplineRequirementType.MONO, disciplines=()
        )


class TestRequiresDiscipline:
    def test_mono_matches_its_single_discipline(self):
        # Slam, krcg id 101798: `[pot]`/`[POT]`.
        requirement = DisciplineRequirement(
            type=DisciplineRequirementType.MONO, disciplines=("pot",)
        )
        assert requires_discipline(requirement, "pot") is True
        assert requires_discipline(requirement, "dom") is False

    def test_choice_matches_any_listed_discipline(self):
        # Line Brawl, krcg id 102229: `[cel]`/`[pot]`/`[pre]`.
        requirement = DisciplineRequirement(
            type=DisciplineRequirementType.CHOICE, disciplines=("cel", "pot", "pre")
        )
        assert requires_discipline(requirement, "cel") is True
        assert requires_discipline(requirement, "pot") is True
        assert requires_discipline(requirement, "pre") is True
        assert requires_discipline(requirement, "dom") is False

    def test_combo_matches_either_required_discipline(self):
        # Forced March: `[cel][for]`/`[CEL][FOR]`.
        requirement = DisciplineRequirement(
            type=DisciplineRequirementType.COMBO, disciplines=("cel", "for")
        )
        assert requires_discipline(requirement, "cel") is True
        assert requires_discipline(requirement, "for") is True
        assert requires_discipline(requirement, "pot") is False

    def test_no_requirement_never_matches(self):
        # Parity Shift (Political Action), krcg id 101353: no discipline symbol.
        requirement = DisciplineRequirement()
        assert requires_discipline(requirement, "dom") is False

    def test_case_insensitive_on_the_queried_discipline(self):
        # Bonding's superior clause is printed "[DOM]"; krcg's own data is
        # already lowercase-canonical, but a caller may pass the printed
        # bracket token as-is.
        requirement = DisciplineRequirement(
            type=DisciplineRequirementType.MONO, disciplines=("dom",)
        )
        assert requires_discipline(requirement, "DOM") is True
        assert requires_discipline(requirement, "dom") is True
