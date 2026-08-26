import random

from drawing_check.generator import build_baseline_set, build_next_set
from drawing_check.release_check import check_release, check_revision_entries

SHEET_COUNT = 620


def test_over_a_600_sheet_synthetic_set_compared_sheet_by_sheet():
    rng = random.Random(3)
    baseline_contents, baseline_parsed = build_baseline_set(rng, count=SHEET_COUNT)
    assert len(baseline_parsed) > 600

    numbers = list(baseline_contents)
    seeded_defects = numbers[:20]
    properly_revised = numbers[20:120]

    current = build_next_set(rng, baseline_contents, seeded_defects, properly_revised)
    assert len(current) == SHEET_COUNT  # every sheet was actually compared, none skipped

    defects = check_revision_entries(baseline_parsed, current)
    assert {d.sheet_number for d in defects} == set(seeded_defects)

    result = check_release(
        baseline_parsed, current, transmittal=set(numbers), sheet_index=set(numbers)
    )
    assert result.releasable is False
    assert len(result.changed_without_revision) == 20
