"""Tests for the scanner engine: CANNOT_SCAN rules, concurrency and the real snapshot."""

import time
from pathlib import Path

from app.checks import CANNOT_SCAN, FAIL, PASS
from app.scanner import load_inventory, run_scan
from app.scoring import score_of, status_counts

REAL_INVENTORY = Path(__file__).resolve().parents[2] / "data" / "inventory.json"


def account(**overrides):
    return {"provider": "aws", "account_id": "111", "name": "t", "simulated_latency_ms": 0,
            "errors": {}, "resources": {}, **overrides}


def inventory(*accounts):
    return {"snapshot_taken_at": "2026-10-01T00:00:00Z", "accounts": list(accounts)}


def test_errored_collection_gives_one_cannot_scan_per_check():
    findings = run_scan(inventory(account(errors={"iam_users": "AccessDenied"})))
    iam = [f for f in findings if f["check_id"].startswith("AWS-IAM")]
    assert len(iam) == 2  # AWS-IAM-01 and AWS-IAM-02 both read iam_users
    for finding in iam:
        assert finding["status"] == CANNOT_SCAN
        assert finding["details"] == "AccessDenied"
        assert finding["resource_id"] is None


def test_missing_collection_gives_no_findings():
    assert run_scan(inventory(account())) == []


def test_bad_record_does_not_stop_the_scan():
    groups = [
        {"group_id": "bad", "ingress": [{"protocol": "tcp", "from_port": "x", "to_port": 22,
                                         "cidrs": ["0.0.0.0/0"]}]},
        {"group_id": "good", "ingress": []},
    ]
    findings = run_scan(inventory(account(resources={"security_groups": groups})))
    statuses = {f["resource_id"]: f["status"] for f in findings}
    assert statuses == {"bad": CANNOT_SCAN, "good": PASS}


def test_only_requested_accounts_are_scanned():
    findings = run_scan(
        inventory(
            account(account_id="a", resources={"rds_instances": [{"db_instance_id": "x",
                                                                   "publicly_accessible": True}]}),
            account(account_id="b", resources={"rds_instances": [{"db_instance_id": "y",
                                                                   "publicly_accessible": True}]}),
        ),
        account_ids=["b"],
    )
    assert [f["account_id"] for f in findings] == ["b"]


def test_accounts_are_scanned_concurrently():
    slow = [account(account_id=str(i), simulated_latency_ms=300) for i in range(4)]
    start = time.monotonic()
    run_scan(inventory(*slow), workers=4)
    assert time.monotonic() - start < 0.6  # serial would take 1.2s


def test_real_snapshot_results():
    start = time.monotonic()
    findings = run_scan(load_inventory(str(REAL_INVENTORY)), workers=4)
    elapsed = time.monotonic() - start

    assert 2.9 < elapsed < 4  # bounded by the slowest account (3s), not the 8s total
    assert status_counts(findings) == {PASS: 27, FAIL: 18, CANNOT_SCAN: 4}
    assert score_of(findings) == 60.0


def test_score_is_none_without_pass_or_fail():
    assert score_of([{"status": CANNOT_SCAN}]) is None
