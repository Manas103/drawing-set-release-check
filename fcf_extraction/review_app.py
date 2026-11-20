"""FastAPI review console: lists queued (low-confidence or grammar-rejected)
feature control frames and accepts a human correction for each. Every
correction is persisted both as the record's resolution and as a new row
in `correction_label`, so corrections are retrainable labels, not just a
closed ticket."""

from __future__ import annotations

import datetime
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import review_db

_DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "review.db")

app = FastAPI(title="FCF Review Console")


def _db_path() -> str:
    # read per call, not at import time: tests point this at a temp DB via
    # the environment variable after the module has already been imported
    return os.environ.get("FCF_REVIEW_DB", _DEFAULT_DB_PATH)


class Correction(BaseModel):
    final_type: str
    final_value: float
    final_datums: list
    diametral: bool
    corrected_by: str = "engineer"


@app.get("/queue")
def get_queue(sheet_id: str | None = None):
    with review_db.connect(_db_path()) as conn:
        return review_db.queued_items(conn, sheet_id=sheet_id)


@app.post("/queue/{crop_id}/correct")
def correct(crop_id: str, correction: Correction):
    with review_db.connect(_db_path()) as conn:
        try:
            review_db.apply_correction(
                conn,
                crop_id=crop_id,
                final_type=correction.final_type,
                final_value=correction.final_value,
                final_datums=correction.final_datums,
                diametral=correction.diametral,
                corrected_by=correction.corrected_by,
                now=datetime.datetime.utcnow().isoformat(),
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
    return {"crop_id": crop_id, "status": "human_corrected"}


@app.get("/sheets/{sheet_id}/releasable")
def releasable(sheet_id: str):
    with review_db.connect(_db_path()) as conn:
        ok, blocking = review_db.sheet_is_releasable(conn, sheet_id)
    return {"sheet_id": sheet_id, "releasable": ok, "blocking_crop_ids": blocking}
