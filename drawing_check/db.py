"""SQLite storage for issued drawing sets, transmittals and sheet indexes.
Plain `sqlite3`, no ORM: three small tables are the whole schema.
"""
from __future__ import annotations

import sqlite3

from .sheet_pdf import ParsedSheet

SCHEMA = """
CREATE TABLE IF NOT EXISTS issued_sheets (
    set_label TEXT NOT NULL,
    sheet_number TEXT NOT NULL,
    title TEXT NOT NULL,
    discipline TEXT NOT NULL,
    revision INTEGER NOT NULL,
    revision_date TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    PRIMARY KEY (set_label, sheet_number)
);

CREATE TABLE IF NOT EXISTS transmittal_sheets (
    set_label TEXT NOT NULL,
    sheet_number TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sheet_index_entries (
    set_label TEXT NOT NULL,
    sheet_number TEXT NOT NULL
);
"""


def connect(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def record_issued_set(conn: sqlite3.Connection, set_label: str, sheets: list[ParsedSheet]) -> None:
    conn.executemany(
        """INSERT OR REPLACE INTO issued_sheets
           (set_label, sheet_number, title, discipline, revision, revision_date, content_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (set_label, s.sheet_number, s.title, s.discipline, s.revision, s.revision_date, s.content_hash)
            for s in sheets
        ],
    )
    conn.commit()


def load_issued_set(conn: sqlite3.Connection, set_label: str) -> dict:
    """Returns {sheet_number: ParsedSheet}."""
    rows = conn.execute(
        "SELECT sheet_number, title, discipline, revision, revision_date, content_hash "
        "FROM issued_sheets WHERE set_label = ?",
        (set_label,),
    ).fetchall()
    return {
        sheet_number: ParsedSheet(sheet_number, title, discipline, revision, revision_date, content_hash)
        for sheet_number, title, discipline, revision, revision_date, content_hash in rows
    }


def record_transmittal(conn: sqlite3.Connection, set_label: str, sheet_numbers: list[str]) -> None:
    conn.executemany(
        "INSERT INTO transmittal_sheets (set_label, sheet_number) VALUES (?, ?)",
        [(set_label, s) for s in sheet_numbers],
    )
    conn.commit()


def load_transmittal(conn: sqlite3.Connection, set_label: str) -> set:
    rows = conn.execute(
        "SELECT sheet_number FROM transmittal_sheets WHERE set_label = ?", (set_label,)
    ).fetchall()
    return {r[0] for r in rows}


def record_sheet_index(conn: sqlite3.Connection, set_label: str, sheet_numbers: list[str]) -> None:
    conn.executemany(
        "INSERT INTO sheet_index_entries (set_label, sheet_number) VALUES (?, ?)",
        [(set_label, s) for s in sheet_numbers],
    )
    conn.commit()


def load_sheet_index(conn: sqlite3.Connection, set_label: str) -> set:
    rows = conn.execute(
        "SELECT sheet_number FROM sheet_index_entries WHERE set_label = ?", (set_label,)
    ).fetchall()
    return {r[0] for r in rows}
