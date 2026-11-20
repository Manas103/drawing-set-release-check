"""SQLite persistence for the FCF review queue: every feature control
frame extracted from a sheet gets exactly one row, and that row can only
move from "queued" to "accepted" through an explicit decision (either the
calibrated auto-accept at extraction time, or a human correction through
the review console). A sheet with any row still "queued" is not
releasable; see `sheet_is_releasable`.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS fcf_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id TEXT NOT NULL,
    crop_id TEXT NOT NULL UNIQUE,
    predicted_type TEXT,
    predicted_value REAL,
    predicted_datums TEXT,
    predicted_diametral INTEGER,
    confidence REAL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'auto_accepted', 'human_corrected')),
    final_type TEXT,
    final_value REAL,
    final_datums TEXT,
    final_diametral INTEGER,
    corrected_by TEXT,
    corrected_at TEXT
);

CREATE TABLE IF NOT EXISTS correction_label (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crop_id TEXT NOT NULL,
    final_type TEXT NOT NULL,
    final_value REAL NOT NULL,
    final_datums TEXT NOT NULL,
    final_diametral INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


@contextmanager
def connect(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_prediction(conn, sheet_id, crop_id, predicted_type, predicted_value, predicted_datums,
                       predicted_diametral, confidence, auto_accept: bool):
    status = "auto_accepted" if auto_accept else "queued"
    final = (predicted_type, predicted_value, ",".join(sorted(predicted_datums)), int(predicted_diametral)) \
        if auto_accept else (None, None, None, None)
    conn.execute(
        """INSERT INTO fcf_record
           (sheet_id, crop_id, predicted_type, predicted_value, predicted_datums, predicted_diametral,
            confidence, status, final_type, final_value, final_datums, final_diametral)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (sheet_id, crop_id, predicted_type, predicted_value, ",".join(sorted(predicted_datums)),
         int(predicted_diametral), confidence, status, *final),
    )


def queued_items(conn, sheet_id=None):
    if sheet_id is None:
        rows = conn.execute("SELECT * FROM fcf_record WHERE status = 'queued'").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM fcf_record WHERE status = 'queued' AND sheet_id = ?", (sheet_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def apply_correction(conn, crop_id, final_type, final_value, final_datums, diametral, corrected_by, now):
    """A human correction resolves a queued row to 'human_corrected' and
    appends a row to correction_label: the review console's corrections
    becoming new labels, not just resolving the queue, is the point."""
    cur = conn.execute("SELECT id FROM fcf_record WHERE crop_id = ? AND status = 'queued'", (crop_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"no queued record for crop_id={crop_id!r}")

    datum_str = ",".join(sorted(final_datums))
    conn.execute(
        """UPDATE fcf_record SET status = 'human_corrected', final_type = ?, final_value = ?,
           final_datums = ?, final_diametral = ?, corrected_by = ?, corrected_at = ?
           WHERE crop_id = ?""",
        (final_type, final_value, datum_str, int(diametral), corrected_by, now, crop_id),
    )
    conn.execute(
        """INSERT INTO correction_label (crop_id, final_type, final_value, final_datums, final_diametral, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (crop_id, final_type, final_value, datum_str, int(diametral), now),
    )


def sheet_is_releasable(conn, sheet_id) -> tuple:
    """A sheet releases only when every one of its FCFs has a recorded
    decision (auto-accepted or human-corrected); any row still 'queued'
    blocks release and is named."""
    rows = conn.execute(
        "SELECT crop_id, status FROM fcf_record WHERE sheet_id = ?", (sheet_id,)
    ).fetchall()
    blocking = [dict(r)["crop_id"] for r in rows if dict(r)["status"] == "queued"]
    return (len(blocking) == 0, blocking)
