from fcf_extraction.evaluate import exact_match, field_level_exact_match_rate, normalize


def _truth(type_name="position", value=0.05, datums=("A", "B"), diametral=True):
    return {"type": type_name, "value": value, "datums": datums, "diametral": diametral}


def test_exact_match_requires_every_field():
    truth = _truth()
    assert exact_match(normalize("position", 0.05, ("A", "B"), True), truth) is True
    assert exact_match(normalize("position", 0.05, ("A", "C"), True), truth) is False  # wrong datum
    assert exact_match(normalize("position", 0.06, ("A", "B"), True), truth) is False  # wrong value
    assert exact_match(normalize("flatness", 0.05, ("A", "B"), True), truth) is False  # wrong type
    assert exact_match(normalize("position", 0.05, ("A", "B"), False), truth) is False  # wrong modifier


def test_right_value_wrong_datum_is_not_a_match():
    truth = _truth(datums=("A",))
    pred = normalize("position", 0.05, ("B",), True)
    assert exact_match(pred, truth) is False


def test_none_prediction_never_matches():
    assert exact_match(None, _truth()) is False


def test_value_rounding_tolerates_float_noise():
    truth = _truth(value=0.050000001)
    pred = normalize("position", 0.05, ("A", "B"), True)
    assert exact_match(pred, truth) is True


def test_field_level_rate_over_a_batch():
    truths = [_truth(), _truth(type_name="flatness", datums=(), diametral=False)]
    preds = [
        normalize("position", 0.05, ("A", "B"), True),  # correct
        normalize("flatness", 0.99, (), False),  # wrong value
    ]
    assert field_level_exact_match_rate(preds, truths) == 0.5
