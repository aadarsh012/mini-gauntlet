"""The scanner engine: reads the inventory and runs every check over every account."""

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from .checks import CANNOT_SCAN, CHECKS, CannotScan, Check

logger = logging.getLogger("scanner")

DEFAULT_WORKERS = 4


def inventory_path() -> str:
    return os.environ.get("INVENTORY_PATH", "data/inventory.json")


def worker_count() -> int:
    return int(os.environ.get("SCAN_WORKERS", DEFAULT_WORKERS))


def load_inventory(path: str | None = None) -> dict:
    """Read and lightly validate the snapshot. Raises if the file is unusable."""
    with open(path or inventory_path(), encoding="utf-8") as file:
        inventory = json.load(file)
    if not isinstance(inventory, dict) or not isinstance(inventory.get("accounts"), list):
        raise ValueError("inventory must be an object with an 'accounts' list")
    parse_time(inventory.get("snapshot_taken_at"))  # fail early on a bad timestamp
    return inventory


def parse_time(value) -> datetime:
    """Parse an ISO 8601 UTC timestamp like 2026-10-01T00:00:00Z."""
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def make_finding(check: Check, account: dict, status: str, details: str,
                 resource_id=None, region=None) -> dict:
    return {
        "check_id": check.id,
        "title": check.title,
        "provider": check.provider,
        "account_id": str(account.get("account_id")),
        "region": region if isinstance(region, str) else None,
        "resource_id": str(resource_id) if resource_id is not None else None,
        "status": status,
        "severity": check.severity,
        "details": details,
    }


def run_check_on_resource(check: Check, account: dict, resource, snapshot_time: datetime) -> dict:
    """Run one check on one resource. Never raises: problems become CANNOT_SCAN."""
    if not isinstance(resource, dict):
        logger.warning("%s: resource is not an object: %r", check.id, resource)
        return make_finding(check, account, CANNOT_SCAN, "Resource record is not an object")

    resource_id = resource.get(check.id_field)
    region = resource.get("region")
    if resource_id is None:
        logger.warning("%s: resource has no '%s'", check.id, check.id_field)
        return make_finding(check, account, CANNOT_SCAN,
                            f"Resource has no '{check.id_field}' field", region=region)
    try:
        status, details = check.run(resource, snapshot_time)
    except CannotScan as error:
        logger.warning("%s on %s: cannot scan: %s", check.id, resource_id, error)
        status, details = CANNOT_SCAN, f"Cannot evaluate: {error}"
    except Exception as error:  # a buggy check must never stop the scan
        logger.warning("%s on %s crashed: %r", check.id, resource_id, error)
        status, details = CANNOT_SCAN, f"Check failed unexpectedly: {type(error).__name__}"
    return make_finding(check, account, status, details, resource_id, region)


def scan_account(account: dict, snapshot_time: datetime) -> list[dict]:
    """Scan a single account: wait the simulated latency, then run its provider's checks."""
    latency_ms = account.get("simulated_latency_ms", 0)
    if isinstance(latency_ms, (int, float)) and latency_ms > 0:
        time.sleep(latency_ms / 1000)

    errors = account.get("errors") or {}
    resources = account.get("resources") or {}
    findings = []

    for check in CHECKS:
        if check.provider != account.get("provider"):
            continue
        if check.collection in errors:
            # The whole collection couldn't be read: one CANNOT_SCAN for the account.
            findings.append(make_finding(check, account, CANNOT_SCAN, str(errors[check.collection])))
            continue
        items = resources.get(check.collection, [])
        if not isinstance(items, list):
            findings.append(make_finding(check, account, CANNOT_SCAN,
                                         f"Collection '{check.collection}' is not a list"))
            continue
        for resource in items:
            findings.append(run_check_on_resource(check, account, resource, snapshot_time))
    return findings


def run_scan(inventory: dict, account_ids: list[str] | None = None,
             workers: int | None = None) -> list[dict]:
    """Scan the chosen accounts (all of them when account_ids is None) concurrently."""
    snapshot_time = parse_time(inventory["snapshot_taken_at"])
    accounts = [a for a in inventory["accounts"]
                if account_ids is None or str(a.get("account_id")) in account_ids]

    with ThreadPoolExecutor(max_workers=workers or worker_count()) as pool:
        results = pool.map(lambda account: scan_account(account, snapshot_time), accounts)
        return [finding for account_findings in results for finding in account_findings]
