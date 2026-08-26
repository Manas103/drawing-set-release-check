import random

from drawing_check.db import (
    connect,
    load_issued_set,
    load_sheet_index,
    load_transmittal,
    record_issued_set,
    record_sheet_index,
    record_transmittal,
)
from drawing_check.generator import build_baseline_set
from drawing_check.release_check import check_release


def test_issued_set_persists_and_reloads_through_sqlite():
    rng = random.Random(9)
    _, parsed = build_baseline_set(rng, count=10)
    conn = connect(":memory:")

    record_issued_set(conn, "2026-01-issue", list(parsed.values()))
    reloaded = load_issued_set(conn, "2026-01-issue")

    assert set(reloaded) == set(parsed)
    for number, sheet in parsed.items():
        assert reloaded[number] == sheet


def test_transmittal_and_index_persist_through_sqlite_and_drive_the_release_check():
    conn = connect(":memory:")
    record_transmittal(conn, "release-1", ["A-101", "A-102", "A-103"])
    record_sheet_index(conn, "release-1", ["A-101", "A-102"])

    transmittal = load_transmittal(conn, "release-1")
    sheet_index = load_sheet_index(conn, "release-1")

    result = check_release(previous={}, current={}, transmittal=transmittal, sheet_index=sheet_index)
    assert result.releasable is False
    assert result.transmittal_only == ("A-103",)
