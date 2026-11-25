"""SQLite storage for scans and findings, using only the standard library."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    status      TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    account_ids TEXT NOT NULL,   -- JSON list
    error       TEXT
);
CREATE TABLE IF NOT EXISTS findings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id     INTEGER NOT NULL REFERENCES scans(id),
    check_id    TEXT NOT NULL,
    title       TEXT NOT NULL,
    provider    TEXT NOT NULL,
    account_id  TEXT NOT NULL,
    region      TEXT,
    resource_id TEXT,
    status      TEXT NOT NULL,
    severity    TEXT NOT NULL,
    details     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS findings_scan_id ON findings(scan_id);
"""

FINDING_COLUMNS = ["check_id", "title", "provider", "account_id", "region",
                   "resource_id", "status", "severity", "details"]

# FAIL first, then CANNOT_SCAN, then PASS; CRITICAL first, LOW last.
FINDINGS_ORDER = """
ORDER BY
  CASE status WHEN 'FAIL' THEN 0 WHEN 'CANNOT_SCAN' THEN 1 ELSE 2 END,
  CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
  check_id,
  resource_id
"""


def db_path() -> str:
    return os.environ.get("DB_PATH", "mini_gauntlet.db")


@contextmanager
def connect():
    """Open a connection, commit on success (rollback on error) and always close it."""
    connection = sqlite3.connect(db_path())
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    """Create tables, and mark scans left RUNNING by a restart as FAILED."""
    directory = os.path.dirname(db_path())
    if directory:
        os.makedirs(directory, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.execute(
            "UPDATE scans SET status = 'FAILED', finished_at = ?, error = ? WHERE status = 'RUNNING'",
            (now(), "Server restarted while the scan was running"),
        )


def create_scan(account_ids: list[str]) -> int:
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO scans (status, started_at, account_ids) VALUES ('RUNNING', ?, ?)",
            (now(), json.dumps(account_ids)),
        )
        return cursor.lastrowid


def complete_scan(scan_id: int, findings: list[dict]) -> None:
    rows = [(scan_id, *[f[col] for col in FINDING_COLUMNS]) for f in findings]
    with connect() as conn:
        conn.executemany(
            f"INSERT INTO findings (scan_id, {', '.join(FINDING_COLUMNS)}) "
            f"VALUES (?, {', '.join('?' for _ in FINDING_COLUMNS)})",
            rows,
        )
        conn.execute("UPDATE scans SET status = 'COMPLETED', finished_at = ? WHERE id = ?",
                     (now(), scan_id))


def fail_scan(scan_id: int, error: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE scans SET status = 'FAILED', finished_at = ?, error = ? WHERE id = ?",
                     (now(), error, scan_id))


def scan_to_dict(row: sqlite3.Row) -> dict:
    scan = dict(row)
    scan["account_ids"] = json.loads(scan["account_ids"])
    return scan


def list_scans() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM scans ORDER BY id DESC").fetchall()
    return [scan_to_dict(row) for row in rows]


def get_scan(scan_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    return scan_to_dict(row) if row else None


def all_findings(scan_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM findings WHERE scan_id = ?", (scan_id,)).fetchall()
    return [dict(row) for row in rows]


def query_findings(scan_id: int, filters: dict, page: int, page_size: int) -> tuple[list[dict], int]:
    """Filtered, ordered, paginated findings. Filters compare case-insensitively."""
    where = ["scan_id = ?"]
    params: list = [scan_id]
    for column, value in filters.items():
        if value:
            where.append(f"LOWER({column}) = LOWER(?)")  # column names come from our code only
            params.append(value)
    where_sql = " AND ".join(where)

    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM findings WHERE {where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM findings WHERE {where_sql} {FINDINGS_ORDER} LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()
    return [dict(row) for row in rows], total
