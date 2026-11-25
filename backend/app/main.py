"""REST API for Mini Gauntlet."""

import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from pydantic import BaseModel

from . import db
from .checks import CHECKS, FAIL, PASS
from .scanner import load_inventory, run_scan
from .scoring import fail_counts_by_severity, score, score_of, status_counts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Mini Gauntlet", lifespan=lifespan)


class ScanRequest(BaseModel):
    account_ids: list[str] | None = None


# ---------- background job ----------

def execute_scan(scan_id: int, account_ids: list[str] | None) -> None:
    """Runs in the background. Any crash marks the whole scan FAILED."""
    try:
        inventory = load_inventory()
        findings = run_scan(inventory, account_ids)
        db.complete_scan(scan_id, findings)
        logger.info("scan %s completed with %d findings", scan_id, len(findings))
    except Exception as error:
        logger.exception("scan %s failed", scan_id)
        db.fail_scan(scan_id, f"{type(error).__name__}: {error}")


# ---------- response helpers ----------

def scan_summary(scan: dict, findings: list[dict]) -> dict:
    counts = status_counts(findings)
    return {**scan, "score": score(counts[PASS], counts[FAIL]), "counts": counts}


def scan_detail(scan: dict, findings: list[dict]) -> dict:
    detail = scan_summary(scan, findings)
    detail["fail_counts_by_severity"] = fail_counts_by_severity(findings)
    detail["account_scores"] = [
        {
            "account_id": account_id,
            "score": score_of([f for f in findings if f["account_id"] == account_id]),
        }
        for account_id in scan["account_ids"]
    ]
    return detail


# ---------- routes ----------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/checks")
def list_checks():
    return [
        {
            "id": check.id,
            "title": check.title,
            "severity": check.severity,
            "provider": check.provider,
            "collection": check.collection,
            "resource_id_field": check.id_field,
        }
        for check in CHECKS
    ]


@app.post("/api/scans", status_code=202)
def start_scan(background_tasks: BackgroundTasks, request: ScanRequest | None = None):
    requested = request.account_ids if request else None
    if requested is not None and len(requested) == 0:
        raise HTTPException(422, "account_ids must not be empty")

    try:
        known = [str(a.get("account_id")) for a in load_inventory()["accounts"]]
    except Exception:
        # Can't read the snapshot: still create the scan, it will be marked FAILED.
        known = None

    if known is not None and requested is not None:
        unknown = [a for a in requested if a not in known]
        if unknown:
            raise HTTPException(422, f"unknown account_ids: {unknown}")

    account_ids = requested if requested is not None else (known or [])
    scan_id = db.create_scan(account_ids)
    background_tasks.add_task(execute_scan, scan_id, requested)
    return scan_summary(db.get_scan(scan_id), [])


@app.get("/api/scans")
def list_scans():
    return [scan_summary(scan, db.all_findings(scan["id"])) for scan in db.list_scans()]


def get_scan_or_404(scan_id: int) -> dict:
    scan = db.get_scan(scan_id)
    if scan is None:
        raise HTTPException(404, "scan not found")
    return scan


@app.get("/api/scans/{scan_id}")
def read_scan(scan_id: int):
    scan = get_scan_or_404(scan_id)
    return scan_detail(scan, db.all_findings(scan_id))


@app.get("/api/scans/{scan_id}/findings")
def read_findings(
    scan_id: int,
    status: str | None = None,
    severity: str | None = None,
    provider: str | None = None,
    account_id: str | None = None,
    check_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    get_scan_or_404(scan_id)
    filters = {"status": status, "severity": severity, "provider": provider,
               "account_id": account_id, "check_id": check_id}
    items, total = db.query_findings(scan_id, filters, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}
