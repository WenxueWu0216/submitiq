"""API round trip on a temporary SQLite database."""
import importlib

import pytest
from fastapi.testclient import TestClient

from evals.run import list_packages


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 't.db'}")
    monkeypatch.setenv("SUBMITIQ_STORAGE", str(tmp_path / "uploads"))
    import service.app as appmod
    importlib.reload(appmod)
    return TestClient(appmod.app)


def _upload(client, pkg):
    files = [("files", (p.name, p.read_bytes())) for p in sorted(pkg.iterdir()) if p.name != "ground_truth.json"]
    return client.post("/submissions", files=files)


def test_upload_review_correct_approve_export(client):
    pkg = next(p for p in list_packages("dev") if p.name == "SUB-0059")   # scanned SOV with a missing PPC
    r = _upload(client, pkg)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "needs_review" and body["flagged_fields"] > 0
    sub_id = body["id"]

    queue = client.get("/review-queue").json()
    assert queue[0]["id"] == sub_id

    detail = client.get(f"/submissions/{sub_id}").json()["result"]
    flagged = [p for p, fp in detail["provenance"].items() if fp["status"] != "ok"]
    assert flagged

    bad = client.post(f"/submissions/{sub_id}/review", json={"reviewer": "uw1", "corrections": [{"path": "nope.x", "value": 1}]})
    assert bad.status_code == 422

    fix = client.post(f"/submissions/{sub_id}/review", json={
        "reviewer": "uw1", "action": "correct",
        "corrections": [{"path": "locations[1].protection_class", "value": "4", "comment": "per broker email"}]})
    assert fix.status_code == 200
    after = client.get(f"/submissions/{sub_id}").json()["result"]
    assert after["provenance"]["locations[1].protection_class"]["extractor"] == "human:uw1"
    loc1 = next(l for l in after["record"]["locations"] if l["loc_number"] == 1)
    assert loc1["protection_class"] == 4

    assert client.get(f"/submissions/{sub_id}/eval-case").status_code == 409   # not approved yet
    ok = client.post(f"/submissions/{sub_id}/review", json={"reviewer": "uw1", "action": "approve"})
    assert ok.json()["status"] == "approved"
    case = client.get(f"/submissions/{sub_id}/eval-case").json()
    assert case["meta"]["split"] == "reviewed" and case["record"]["locations"]

    corr = client.get("/corrections").json()
    assert corr[0]["field"] == "locations[1].protection_class" and corr[0]["new"] == 4


def test_ui_pages_render(client):
    pkg = list_packages("dev")[0]
    sub_id = _upload(client, pkg).json()["id"]
    assert "Submissions" in client.get("/").text
    page = client.get(f"/ui/submissions/{sub_id}").text
    assert "Recommendation" in page and "insured.named_insured" in page
    row = client.post(f"/ui/submissions/{sub_id}/fields", data={"path": "insured.dba", "value": "Test DBA"})
    assert row.status_code == 200 and "human:underwriter" in row.text
