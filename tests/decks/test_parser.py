"""Plain-text decklist parsing (`vtesbot.decks.parser`).

Per the `deck-validation` skill: accept `2x Card Name` / `2 Card Name`
lines under `Crypt`/`Library` headers; report an unparseable line with its
line number instead of skipping it.
"""

from vtesbot.decks import parse_decklist


def test_parses_crypt_and_library_sections():
    text = """\
Crypt
2x Alexa Draper
1 Queen Anne

Library
3x Enchant Kindred
2 Bonding
"""
    parsed = parse_decklist(text)

    assert [(line.count, line.name) for line in parsed.crypt] == [
        (2, "Alexa Draper"),
        (1, "Queen Anne"),
    ]
    assert [(line.count, line.name) for line in parsed.library] == [
        (3, "Enchant Kindred"),
        (2, "Bonding"),
    ]
    assert parsed.errors == []


def test_accepts_count_without_x_suffix():
    parsed = parse_decklist("Crypt\n4 Alexa Draper\n")
    assert parsed.crypt[0].count == 4
    assert parsed.crypt[0].name == "Alexa Draper"


def test_blank_lines_and_comments_are_skipped():
    text = """\
Crypt
# a comment
2x Alexa Draper

// another comment
"""
    parsed = parse_decklist(text)
    assert len(parsed.crypt) == 1
    assert parsed.errors == []


def test_unparseable_line_is_reported_with_its_line_number():
    text = """\
Crypt
2x Alexa Draper
this is not a valid decklist line
1x Queen Anne
"""
    parsed = parse_decklist(text)

    assert len(parsed.errors) == 1
    error = parsed.errors[0]
    assert error.line_no == 3
    assert error.text == "this is not a valid decklist line"
    # the line before and after the bad one are still parsed
    assert [line.name for line in parsed.crypt] == ["Alexa Draper", "Queen Anne"]


def test_card_line_before_any_header_is_reported_as_an_error():
    parsed = parse_decklist("2x Alexa Draper\n")
    assert len(parsed.errors) == 1
    assert parsed.errors[0].line_no == 1
    assert parsed.crypt == []
    assert parsed.library == []


def test_section_header_is_case_insensitive():
    parsed = parse_decklist("CRYPT\n1 Alexa Draper\nlibrary\n1 Bonding\n")
    assert len(parsed.crypt) == 1
    assert len(parsed.library) == 1
