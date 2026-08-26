"""End-to-end demo: build a small issued set, persist it to SQLite, build a
next set with one seeded defect and one legitimate revision, check it
(refused), fix the defect, check again (still refused: transmittal
disagrees with the sheet index), fix the transmittal, check again
(allowed).
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from drawing_check.db import connect, load_issued_set, record_issued_set
from drawing_check.generator import build_baseline_set, build_next_set
from drawing_check.release_check import check_release


def main():
    rng = random.Random(77)
    conn = connect(":memory:")

    baseline_contents, baseline_parsed = build_baseline_set(rng, count=8)
    record_issued_set(conn, "2026-01-issue", list(baseline_parsed.values()))
    numbers = list(baseline_contents)
    print(f"issued set '2026-01-issue': {len(numbers)} sheets: {numbers}")

    # A-101 changes with no revision bump (a real defect); S-201 changes
    # and is properly revisioned.
    seeded_defects = [numbers[0]]
    properly_revised = [numbers[1]]
    current = build_next_set(rng, baseline_contents, seeded_defects, properly_revised)

    previous = load_issued_set(conn, "2026-01-issue")
    transmittal = set(numbers)
    sheet_index = set(numbers) - {numbers[-1]}  # last sheet dropped from the index by mistake

    result = check_release(previous, current, transmittal, sheet_index)
    print(f"\ncheck 1: {result.describe()}")
    assert not result.releasable

    print(f"\nfixing sheet {seeded_defects[0]}: bumping its revision to match its real content change...")
    from drawing_check.generator import render_and_parse, revise_sheet

    fixed = revise_sheet(baseline_contents[seeded_defects[0]], bump_revision=True, change_content=True, new_date="2026-03-01", seed_offset=10_000)
    current[seeded_defects[0]] = render_and_parse(fixed)

    result = check_release(previous, current, transmittal, sheet_index)
    print(f"check 2: {result.describe()}")
    assert not result.releasable  # transmittal still disagrees with the index

    print(f"\nfixing the sheet index to include {numbers[-1]}...")
    sheet_index = set(numbers)
    result = check_release(previous, current, transmittal, sheet_index)
    print(f"check 3: {result.describe()}")
    assert result.releasable


if __name__ == "__main__":
    main()
