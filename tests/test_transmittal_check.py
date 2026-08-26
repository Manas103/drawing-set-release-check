from drawing_check.release_check import check_release, check_transmittal_against_index


def test_matching_transmittal_and_index_disagree_on_nothing():
    transmittal_only, index_only = check_transmittal_against_index({"A-101", "A-102"}, {"A-101", "A-102"})
    assert transmittal_only == ()
    assert index_only == ()


def test_transmittal_claims_a_sheet_the_index_does_not_have():
    transmittal_only, index_only = check_transmittal_against_index({"A-101", "A-102", "A-103"}, {"A-101", "A-102"})
    assert transmittal_only == ("A-103",)
    assert index_only == ()


def test_index_lists_a_sheet_the_transmittal_omits():
    transmittal_only, index_only = check_transmittal_against_index({"A-101"}, {"A-101", "A-102"})
    assert transmittal_only == ()
    assert index_only == ("A-102",)


def test_release_refused_when_transmittal_disagrees_with_index_even_with_no_revision_defects():
    result = check_release(
        previous={}, current={}, transmittal={"A-101", "A-102"}, sheet_index={"A-101"}
    )
    assert result.releasable is False
    assert "A-102" in result.describe()


def test_release_allowed_when_everything_agrees_and_nothing_changed():
    result = check_release(previous={}, current={}, transmittal={"A-101"}, sheet_index={"A-101"})
    assert result.releasable is True
    assert "allowed" in result.describe()
