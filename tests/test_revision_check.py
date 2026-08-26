import random

from drawing_check.generator import build_baseline_set, build_next_set
from drawing_check.release_check import check_revision_entries


def test_45_of_45_seeded_release_defects_caught():
    rng = random.Random(1)
    baseline_contents, baseline_parsed = build_baseline_set(rng, count=100)
    numbers = list(baseline_contents)

    seeded_defects = numbers[:45]
    properly_revised = numbers[45:70]  # legitimate changes, must not be flagged
    # numbers[70:] are left completely unchanged

    current = build_next_set(rng, baseline_contents, seeded_defects, properly_revised)
    defects = check_revision_entries(baseline_parsed, current)
    defect_sheet_numbers = {d.sheet_number for d in defects}

    assert defect_sheet_numbers == set(seeded_defects)
    assert len(defects) == 45

    for defect in defects:
        assert defect.sheet_number in defect.describe()
        assert "no new revision entry" in defect.describe()


def test_0_false_holds_across_40_clean_sets():
    false_holds = 0
    for seed in range(40):
        rng = random.Random(2000 + seed)
        baseline_contents, baseline_parsed = build_baseline_set(rng, count=20)
        numbers = list(baseline_contents)
        # Every change in a "clean" set is properly revisioned; some sheets
        # are left untouched entirely. No seeded defects at all.
        properly_revised = numbers[: len(numbers) // 2]
        current = build_next_set(rng, baseline_contents, seeded_defect_sheets=[], properly_revised_sheets=properly_revised)

        defects = check_revision_entries(baseline_parsed, current)
        false_holds += len(defects)

    assert false_holds == 0


def test_sheets_new_to_the_current_set_are_not_flagged():
    rng = random.Random(5)
    baseline_contents, baseline_parsed = build_baseline_set(rng, count=5)
    current = dict(baseline_parsed)
    from drawing_check.sheet_pdf import ParsedSheet

    current["A-999"] = ParsedSheet("A-999", "New Sheet", "architectural", 0, "2026-03-01", "deadbeef")
    defects = check_revision_entries(baseline_parsed, current)
    assert defects == ()
