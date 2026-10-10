"""Vampire sect (OQ-18 Gap 1, `docs/OPEN_QUESTIONS.md`, resolved by this
pass): `Sect` on `engine/cards.py`, and `derive_sect`, the generic helper
that classifies a vampire's sect from its own printed `card_text` preamble.

Sources:
- Rulebook SS6 "Vampire Sects" <https://www.vekn.net/rulebook/6-vampire-sects>
  (re-fetched live 2026-10-10, matching the local cache's `dateModified`
  under `data/sources/rulebook/2026-10-09/6-vampire-sects.md`): "A vampire
  always belongs to one and only one sect." Defines Camarilla, Anarch,
  Sabbat, Independent.
- Rulebook SS7 "Legacy Sets" > "Other Vampire Sects" > "Laibon"
  <https://www.vekn.net/rulebook/7-legacy-sets> (re-fetched live 2026-10-10,
  matching the local cache's `dateModified`): the fifth sect, documented
  separately because its cards predate 5th Edition, not because it is any
  less a sect ("Only Laibon can hold the laibon titles kholo and magaji.").

Card texts below are verbatim, pulled from the installed `krcg` 5.14
package's own `krcg.load()` dataset, 2026-10-10 (one fixed snapshot, pinned
as literal strings here per this project's "no I/O in tests" determinism
convention -- see e.g. `tests/cards/test_enchant_kindred.py`). `krcg_id`s
noted per vampire for traceability.
"""

import pytest

from vtesbot.engine import CryptCard, Sect, UnresolvedRulingError, derive_sect

# Camarilla: Jeremy MacNeil, krcg id 200693.
CAMARILLA_TEXT = "Camarilla."

# Anarch: Aluc Romas de Leon (krcg id 201577), Anita Wainwright (201657),
# Ariane (200132) -- OQ-18's own three named examples.
ANARCH_TEXT_ALUC = "Anarch."
ANARCH_TEXT_ANITA = "Anarch."
ANARCH_TEXT_ARIANE = "Anarch: Ariane gets -1 stealth during undirected actions."

# Sabbat: Aaron Bathurst, krcg id 200002.
SABBAT_TEXT = "Sabbat."

# Independent: Abebe, krcg id 200006. Confirms Independent vampires carry an
# explicit "Independent." preamble in their own printed text, rather than
# being identifiable only by the *absence* of a preamble.
INDEPENDENT_TEXT = "Independent."

# Laibon: Abu Nuwasi, krcg id 200009.
LAIBON_TEXT = "Laibon."

# Advanced printing: Alan Sovereign (Advanced), krcg id 200041 -- the
# "Advanced, <Sect>: ..." convention used by advanced-level vampire
# reprints.
ADVANCED_CAMARILLA_TEXT = (
    "Advanced, Camarilla: While Alan is ready, you may pay some or all of "
    "the pool cost of equipping from any investment cards you control.\n"
    "[MERGED] During your master phase, if Alan is ready, you may move a "
    "counter from any investment card to your pool."
)

# Advanced printing with trailing unrelated clauses after the sect
# preamble's own terminating period, separated by their own sentences:
# Dylan (Advanced), krcg id 200395 (Ventrue antitribu, Sabbat). Confirms
# the sect preamble is still isolated correctly even when further,
# unrelated "Red List." / "Infernal." clauses immediately follow it.
ADVANCED_SABBAT_RED_LIST_TEXT = (
    "Advanced, Sabbat. Red List: Dylan gets +1 stealth when bleeding. +1 strength. Infernal."
)

# Imbued are not vampires and have no sect (Rulebook SS6 only speaks of
# vampires). Jack "Hannibal137" Harmon, krcg id 200656 (Imbued, creed
# "Defender") -- his own printed text does not start with a sect keyword.
IMBUED_TEXT = "Jack gets an optional maneuver on the first round of combat."


class TestSectEnum:
    """`Sect` models exactly the five sects the Rulebook defines."""

    def test_five_sects(self):
        assert {member.value for member in Sect} == {
            "Camarilla",
            "Anarch",
            "Sabbat",
            "Independent",
            "Laibon",
        }


class TestCryptCardSectField:
    """`sect` is a real field on `CryptCard`, defaulting to `None`."""

    def test_default_is_none(self):
        card = CryptCard(krcg_id=1, name="Test Vampire", capacity=5, group=5)
        assert card.sect is None

    def test_can_carry_a_sect(self):
        card = CryptCard(krcg_id=1, name="Test Vampire", capacity=5, group=5, sect=Sect.ANARCH)
        assert card.sect is Sect.ANARCH


class TestDeriveSect:
    """`derive_sect` classifies a vampire's sect from its own card text."""

    @pytest.mark.parametrize(
        ("card_text", "expected"),
        [
            (CAMARILLA_TEXT, Sect.CAMARILLA),
            (ANARCH_TEXT_ALUC, Sect.ANARCH),
            (ANARCH_TEXT_ANITA, Sect.ANARCH),
            (ANARCH_TEXT_ARIANE, Sect.ANARCH),
            (SABBAT_TEXT, Sect.SABBAT),
            (INDEPENDENT_TEXT, Sect.INDEPENDENT),
            (LAIBON_TEXT, Sect.LAIBON),
            (ADVANCED_CAMARILLA_TEXT, Sect.CAMARILLA),
            (ADVANCED_SABBAT_RED_LIST_TEXT, Sect.SABBAT),
        ],
    )
    def test_real_vampire_texts(self, card_text, expected):
        assert derive_sect(card_text) is expected

    def test_title_qualifier_does_not_change_the_sect(self):
        # Quentin King III, krcg id 201141: "Camarilla Prince of Boston."
        assert derive_sect("Camarilla Prince of Boston.") is Sect.CAMARILLA

    def test_imbued_text_has_no_sect_preamble_and_raises(self):
        """Imbued are not vampires (Rulebook SS6); calling `derive_sect` on
        an Imbued's own text must not silently misreport "Independent" --
        it raises instead, per the no-guessing rule (CLAUDE.md SS2)."""
        with pytest.raises(UnresolvedRulingError) as exc_info:
            derive_sect(IMBUED_TEXT)
        assert exc_info.value.oq_id == "OQ-18"

    def test_malformed_or_unrecognised_preamble_raises_rather_than_guesses(self):
        with pytest.raises(UnresolvedRulingError) as exc_info:
            derive_sect("Some future card text with no sect preamble at all.")
        assert exc_info.value.oq_id == "OQ-18"

    def test_empty_text_raises(self):
        with pytest.raises(UnresolvedRulingError):
            derive_sect("")
