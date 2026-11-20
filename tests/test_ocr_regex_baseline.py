from fcf_extraction.ocr_regex_baseline import extract_fields_from_text


def test_extracts_clean_text_exactly():
    fields = extract_fields_from_text("POS 0.05 A B")
    assert fields["type_code"] == "POS"
    assert fields["value"] == 0.05
    assert fields["datums"] == ("A", "B")


def test_diameter_modifier_detected_when_present():
    fields = extract_fields_from_text("POS O0.05 A B")
    assert fields["diametral"] is True


def test_no_diameter_modifier_when_absent():
    fields = extract_fields_from_text("PERP 0.10 A")
    assert fields["diametral"] is False


def test_missing_type_code_returns_none_for_that_field():
    fields = extract_fields_from_text("0.10 A")
    assert fields["type_code"] is None


def test_missing_value_returns_none_for_that_field():
    fields = extract_fields_from_text("POS A B")
    assert fields["value"] is None


def test_no_datum_letters_returns_empty_tuple():
    fields = extract_fields_from_text("FLT 0.16")
    assert fields["datums"] == ()


def test_garbled_ocr_text_does_not_crash():
    fields = extract_fields_from_text("P0S O.05 l1 A8")
    assert isinstance(fields, dict)
