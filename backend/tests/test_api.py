"""API tests. They use the real snapshot with latencies set to 0 so they run fast."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

REAL_INVENTORY = Path(__file__).resolve().parents[2] / "data" / "inventory.json"


@pytest.fixture
def client(tmp_path, monkeypatch):
    data = json.loads(REAL_INVENTORY.read_text())
    for account in data["accounts"]:
        account["simulated_latency_ms"] = 0
    inventory_file = tmp_path / "inventory.json"
    inventory_file.write_text(json.dumps(data))

    monkeypatch.setenv("INVENTORY_PATH", str(inventory_file))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as test_client:  # "with" runs the startup code (creates tables)
        yield test_client


def start_scan(client, body=None) -> dict:
    response = client.post("/api/scans", json=body)
    assert response.status_code == 202
    return response.json()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_checks_catalog(client):
    checks = client.get("/api/checks").json()
    assert len(checks) == 10
    assert {"id", "title", "severity", "provider", "collection"} <= set(checks[0])


def test_start_scan_returns_running_then_completes(client):
    scan = start_scan(client)
    assert scan["status"] == "RUNNING"
    assert len(scan["account_ids"]) == 4

    # TestClient runs background tasks before returning, so the scan is done now.
    detail = client.get(f"/api/scans/{scan['id']}").json()
    assert detail["status"] == "COMPLETED"
    assert detail["counts"] == {"PASS": 27, "FAIL": 18, "CANNOT_SCAN": 4}
    assert detail["score"] == 60.0
    assert detail["fail_counts_by_severity"] == {"CRITICAL": 7, "HIGH": 8, "MEDIUM": 2, "LOW": 1}
    scores = {a["account_id"]: a["score"] for a in detail["account_scores"]}
    assert scores["8f14e45f-ceea-4e7a-9d3b-2f6c1a0b7d21"] == 57.1


def test_scan_for_selected_accounts(client):
    scan = start_scan(client, {"account_ids": ["210987654321"]})
    assert scan["account_ids"] == ["210987654321"]
    findings = client.get(f"/api/scans/{scan['id']}/findings?page_size=100").json()
    assert {f["account_id"] for f in findings["items"]} == {"210987654321"}


def test_list_scans_newest_first(client):
    first = start_scan(client)
    second = start_scan(client)
    scans = client.get("/api/scans").json()
    assert [s["id"] for s in scans] == [second["id"], first["id"]]
    assert scans[0]["score"] == 60.0
    assert scans[0]["counts"]["FAIL"] == 18


def test_empty_account_list_is_422(client):
    assert client.post("/api/scans", json={"account_ids": []}).status_code == 422


def test_unknown_account_is_422(client):
    assert client.post("/api/scans", json={"account_ids": ["nope"]}).status_code == 422


def test_unknown_scan_is_404(client):
    assert client.get("/api/scans/999").status_code == 404
    assert client.get("/api/scans/999/findings").status_code == 404


def test_findings_order(client):
    scan = start_scan(client)
    items = client.get(f"/api/scans/{scan['id']}/findings?page_size=100").json()["items"]
    status_rank = {"FAIL": 0, "CANNOT_SCAN": 1, "PASS": 2}
    severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    keys = [(status_rank[f["status"]], severity_rank[f["severity"]], f["check_id"], f["resource_id"] or "")
            for f in items]
    assert keys == sorted(keys)
    assert items[0]["status"] == "FAIL" and items[0]["severity"] == "CRITICAL"


def test_filters_are_case_insensitive(client):
    scan = start_scan(client)
    url = f"/api/scans/{scan['id']}/findings"
    body = client.get(url, params={"status": "fail", "provider": "AZURE"}).json()
    assert body["total"] == 3
    assert all(f["status"] == "FAIL" and f["provider"] == "azure" for f in body["items"])

    body = client.get(url, params={"severity": "critical", "check_id": "aws-ec2-01"}).json()
    assert body["total"] == 9  # every EC2 finding is CRITICAL, any status


def test_pagination(client):
    scan = start_scan(client)
    url = f"/api/scans/{scan['id']}/findings"
    page1 = client.get(url).json()
    assert page1["page"] == 1 and page1["page_size"] == 25
    assert page1["total"] == 49
    assert len(page1["items"]) == 25

    page2 = client.get(url, params={"page": 2}).json()
    assert len(page2["items"]) == 24
    assert not {f["id"] for f in page1["items"]} & {f["id"] for f in page2["items"]}


def test_page_size_over_100_is_422(client):
    scan = start_scan(client)
    assert client.get(f"/api/scans/{scan['id']}/findings?page_size=101").status_code == 422


def test_unreadable_snapshot_marks_scan_failed(client, monkeypatch, tmp_path):
    monkeypatch.setenv("INVENTORY_PATH", str(tmp_path / "missing.json"))
    scan = start_scan(client)
    detail = client.get(f"/api/scans/{scan['id']}").json()
    assert detail["status"] == "FAILED"
    assert detail["score"] is None
