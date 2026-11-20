import os
import tempfile

import pytest

from fcf_extraction import review_db


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_auto_accepted_prediction_is_immediately_releasable(db_path):
    with review_db.connect(db_path) as conn:
        review_db.insert_prediction(
            conn, "sheet-1", "crop-1", "position", 0.05, ("A", "B"), True, 0.995, auto_accept=True
        )
    with review_db.connect(db_path) as conn:
        ok, blocking = review_db.sheet_is_releasable(conn, "sheet-1")
    assert ok is True
    assert blocking == []


def test_queued_prediction_blocks_release_until_corrected(db_path):
    with review_db.connect(db_path) as conn:
        review_db.insert_prediction(
            conn, "sheet-2", "crop-2", "position", 0.05, ("A",), True, 0.4, auto_accept=False
        )
    with review_db.connect(db_path) as conn:
        ok, blocking = review_db.sheet_is_releasable(conn, "sheet-2")
    assert ok is False
    assert blocking == ["crop-2"]

    with review_db.connect(db_path) as conn:
        review_db.apply_correction(
            conn, "crop-2", "position", 0.05, ("A", "B"), True, "engineer", "2026-01-01T00:00:00"
        )
    with review_db.connect(db_path) as conn:
        ok, blocking = review_db.sheet_is_releasable(conn, "sheet-2")
    assert ok is True
    assert blocking == []


def test_correction_is_recorded_as_a_new_label(db_path):
    with review_db.connect(db_path) as conn:
        review_db.insert_prediction(
            conn, "sheet-3", "crop-3", "flatness", 0.10, (), False, 0.3, auto_accept=False
        )
        review_db.apply_correction(
            conn, "crop-3", "flatness", 0.12, (), False, "engineer", "2026-01-01T00:00:00"
        )
        labels = conn.execute("SELECT * FROM correction_label WHERE crop_id = ?", ("crop-3",)).fetchall()
    assert len(labels) == 1
    assert labels[0]["final_value"] == 0.12


def test_correcting_a_nonexistent_or_already_resolved_record_raises(db_path):
    with review_db.connect(db_path) as conn:
        with pytest.raises(ValueError):
            review_db.apply_correction(
                conn, "nonexistent", "flatness", 0.1, (), False, "engineer", "2026-01-01T00:00:00"
            )


def test_a_sheet_with_multiple_fcfs_needs_every_one_resolved(db_path):
    with review_db.connect(db_path) as conn:
        review_db.insert_prediction(conn, "sheet-4", "c-a", "flatness", 0.1, (), False, 0.99, auto_accept=True)
        review_db.insert_prediction(conn, "sheet-4", "c-b", "position", 0.1, ("A",), True, 0.4, auto_accept=False)
    with review_db.connect(db_path) as conn:
        ok, blocking = review_db.sheet_is_releasable(conn, "sheet-4")
    assert ok is False
    assert blocking == ["c-b"]
