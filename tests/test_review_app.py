import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    os.environ["FCF_REVIEW_DB"] = path

    from fcf_extraction import review_app, review_db

    with review_db.connect(path) as conn:
        review_db.insert_prediction(
            conn, "sheet-1", "crop-1", "position", 0.05, ("A",), True, 0.4, auto_accept=False
        )
        review_db.insert_prediction(
            conn, "sheet-1", "crop-2", "flatness", 0.10, (), False, 0.99, auto_accept=True
        )

    yield TestClient(review_app.app)
    if os.path.exists(path):
        os.remove(path)


def test_queue_lists_only_queued_items(client):
    resp = client.get("/queue")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["crop_id"] == "crop-1"


def test_sheet_not_releasable_while_queue_nonempty(client):
    resp = client.get("/sheets/sheet-1/releasable")
    assert resp.status_code == 200
    body = resp.json()
    assert body["releasable"] is False
    assert body["blocking_crop_ids"] == ["crop-1"]


def test_correction_resolves_queue_and_unblocks_release(client):
    resp = client.post(
        "/queue/crop-1/correct",
        json={"final_type": "position", "final_value": 0.05, "final_datums": ["A", "B"], "diametral": True},
    )
    assert resp.status_code == 200

    assert client.get("/queue").json() == []
    assert client.get("/sheets/sheet-1/releasable").json()["releasable"] is True


def test_correcting_an_unknown_crop_returns_404(client):
    resp = client.post(
        "/queue/does-not-exist/correct",
        json={"final_type": "flatness", "final_value": 0.1, "final_datums": [], "diametral": False},
    )
    assert resp.status_code == 404
