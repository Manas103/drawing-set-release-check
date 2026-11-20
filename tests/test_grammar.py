import pytest

from fcf_extraction.grammar import GrammarError, parse_fcf_string, try_parse_fcf_string


def test_valid_position_frame_parses():
    rec = parse_fcf_string("POS|⌀0.05|AB")
    assert rec.fcf_type == "position"
    assert rec.value == 0.05
    assert rec.datums == ("A", "B")
    assert rec.diametral is True


def test_valid_flatness_frame_with_no_datums_parses():
    rec = parse_fcf_string("FLT|0.16|")
    assert rec.fcf_type == "flatness"
    assert rec.datums == ()
    assert rec.diametral is False


def test_flatness_with_a_datum_is_rejected():
    with pytest.raises(GrammarError):
        parse_fcf_string("FLT|0.16|A")


def test_non_flatness_with_no_datum_is_rejected():
    with pytest.raises(GrammarError):
        parse_fcf_string("PERP|0.10|")


def test_position_without_diameter_modifier_is_rejected():
    with pytest.raises(GrammarError):
        parse_fcf_string("POS|0.05|A")


def test_perpendicularity_with_diameter_modifier_is_rejected():
    with pytest.raises(GrammarError):
        parse_fcf_string("PERP|⌀0.10|A")


def test_unknown_type_code_is_rejected():
    with pytest.raises(GrammarError):
        parse_fcf_string("XYZ|0.10|A")


def test_duplicate_datum_letters_are_rejected():
    with pytest.raises(GrammarError):
        parse_fcf_string("PAR|0.10|AA")


def test_malformed_layout_is_rejected():
    with pytest.raises(GrammarError):
        parse_fcf_string("not an fcf at all")


def test_try_parse_returns_none_instead_of_raising():
    assert try_parse_fcf_string("garbage") is None
    assert try_parse_fcf_string("POS|⌀0.05|AB") is not None


@pytest.mark.parametrize("n_datums", [1, 2, 3])
def test_position_accepts_one_to_three_datums(n_datums):
    letters = "ABCD"[:n_datums]
    rec = parse_fcf_string(f"POS|⌀0.20|{letters}")
    assert len(rec.datums) == n_datums


def test_position_with_four_datums_is_rejected():
    with pytest.raises(GrammarError):
        parse_fcf_string("POS|⌀0.20|ABCD")
