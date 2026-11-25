# Mini Gauntlet

A small cloud posture scanner. It reads a snapshot of AWS, Azure and GCP configuration (`data/inventory.json`), runs ten security checks over it, stores scans and findings in SQLite, serves them over a FastAPI REST API, and shows them in a React + TypeScript dashboard.

**CI:** CI_RUN_LINK

## Run it

```bash
docker compose up --build
```

- Dashboard: http://localhost:3000
- API: http://localhost:8000 (interactive docs at http://localhost:8000/docs)

Click **Run scan**. The scan takes about 3 seconds and the page updates on its own. Scans are stored in the `db-data` volume, so they survive `docker compose down` / `up`. Use `docker compose down -v` to wipe them.

### Configuration (environment variables on the `api` service)

| Variable | Default | Meaning |
|---|---|---|
| `INVENTORY_PATH` | `/app/data/inventory.json` | Snapshot to scan |
| `DB_PATH` | `/data/mini_gauntlet.db` | SQLite file |
| `SCAN_WORKERS` | `4` | Accounts scanned in parallel |

## Run the tests and linters locally

```bash
# backend (Python 3.10+)
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff check . && .venv/bin/pytest

# frontend (Node 20)
cd frontend
npm ci
npm run lint && npx tsc --noEmit && npm test
```

For local development without Docker, run `uvicorn app.main:app --reload` in `backend/` with `INVENTORY_PATH=../data/inventory.json`, and `npm run dev` in `frontend/`. Vite proxies `/api` to port 8000.

## Architecture

```
data/inventory.json ──► scanner engine ──► SQLite ◄── FastAPI ◄── nginx (/api proxy) ◄── React dashboard
```

```
backend/app/
  checks/registry.py   @register_check decorator, CHECKS list, PASS/FAIL/CANNOT_SCAN, CannotScan
  checks/helpers.py    small validators (require_bool, require_port, parse_port_range, ...)
  checks/aws.py        AWS-S3-01, AWS-EC2-01, AWS-IAM-01, AWS-IAM-02, AWS-RDS-01
  checks/azure.py      AZ-STG-01, AZ-NSG-01
  checks/gcp.py        GCP-GCS-01, GCP-GCS-02, GCP-VPC-01
  scanner.py           loads the snapshot, scans accounts in a ThreadPoolExecutor
  scoring.py           score and counts
  db.py                plain sqlite3: schema, inserts, filtered + ordered + paginated findings
  main.py              FastAPI routes and the background scan job
frontend/src/
  api.ts               fetch wrapper (turns network errors into "Cannot reach the API")
  pages/               ScansPage (list + Run scan + polling), ScanPage (summary + findings)
  components/          FindingsTable, Filters, Pagination, CountCards, ScoreBadge, StatusBadge
```

- **Check registry.** A check is one function `(resource, snapshot_time) -> (status, details)` decorated with `@register_check(id, title, severity, provider, collection, id_field)`. To add a check, write the function in the provider's module. Nothing else changes: the scanner, `/api/checks` and the tests all read `CHECKS`.
- **Error handling.** A check raises `CannotScan("why")` when data is malformed. The scanner wraps every (check, resource) call. `CannotScan` *or any unexpected exception* becomes a CANNOT_SCAN finding plus a logged warning, so one bad record (or a buggy check) never stops a scan. A collection listed in `errors` gives one CANNOT_SCAN per check with the error code and no resource ID. A collection that is absent gives no findings.
- **Concurrency.** One thread per account (limit `SCAN_WORKERS`, default 4). Each thread sleeps `simulated_latency_ms` and then runs its checks. The given snapshot takes about 3.0s (the slowest account) instead of 8s.
- **Determinism.** Key age is computed from `snapshot_taken_at`, never the current clock.
- **Scan lifecycle.** `POST /api/scans` validates the request, inserts a `RUNNING` row, returns 202 and runs the scan as a FastAPI background task. Success stores the findings and sets `COMPLETED`. Any exception (e.g. an unreadable snapshot) sets `FAILED` with the error message.
- **Findings order** is done in SQL with `ORDER BY CASE status …, CASE severity …, check_id, resource_id`. Filters compare with `LOWER(col) = LOWER(?)`. All values are bound parameters, and column names come only from code.
- **Untrusted input.** Snapshot strings are stored as-is and rendered only as React text. The ESLint config forbids `dangerouslySetInnerHTML`, and a component test checks that the `<img onerror=…>` description renders as text. Non-numeric or non-boolean fields become CANNOT_SCAN instead of being coerced.
- **Docker.** Both images are multi-stage with pinned bases. The API runs as uid 10001 on `python:3.12.8-slim-bookworm` (~250 MB). The dashboard is static files on `nginx-unprivileged` (~77 MB, runs as `nginx`), which also proxies `/api` to the API, so there's no CORS. Both have health checks, and the dashboard waits for the API to be healthy.

## Assumptions

- **SSH/RDP checks:** the exposed ports are 22 and 3389. A rule exposes them when its source is the whole internet and its port range includes 22 or 3389.
  - AWS: internet means `0.0.0.0/0` or `::/0`. Protocol `tcp`, or `-1` (all protocols and ports, `from_port`/`to_port` ignored). UDP/ICMP rules are ignored, since SSH and RDP are TCP services.
  - Azure: internet means `*`, `Internet`, `Any`, `0.0.0.0/0` or `::/0`. Only `Inbound` + `Allow` rules with protocol `Tcp` or `*` count. Ports can be `*`, a single port, a range, or comma-separated. Deny and Outbound rules are ignored. (No priority evaluation: a higher-priority Deny doesn't cancel an Allow. Noted as a limitation.)
  - GCP: only enabled `INGRESS` rules from `0.0.0.0/0`/`::/0` count. Protocol `tcp` or `all`. A missing `ports` list means all ports. EGRESS and disabled rules PASS.
- **Malformed data:** if any rule in a resource can't be parsed (e.g. `"from_port": "twenty-two"`), the whole resource is CANNOT_SCAN, because we can't be sure it is safe.
- **AWS-S3-01:** `public_access_block: null` means no block is configured, so FAIL (not CANNOT_SCAN).
- **AWS-IAM-01:** users without console access PASS (MFA rule doesn't apply).
- **AWS-IAM-02:** age = whole days between `created_at` and the snapshot. FAIL only if `> 90`, so exactly 90 days PASSes. Inactive keys are ignored. Users with no keys PASS.
- **GCP-GCS-01:** public means a binding to `allUsers` or `allAuthenticatedUsers`, whatever the role.
- **Scores per account** use the same formula over that account's findings. An account with only CANNOT_SCAN findings would get `null` / "N/A".
- **Restart during a scan:** on startup, scans left `RUNNING` are marked `FAILED` ("Server restarted while the scan was running"), since the in-process job is gone.
- **Scan IDs** are auto-increment integers. "Newest first" means highest ID first.
- **Unreadable snapshot at POST time:** the request is accepted (202) and the scan becomes `FAILED`. Account IDs can't be validated without the snapshot.

Expected result for the given snapshot: 49 findings, PASS 27 / FAIL 18 / CANNOT_SCAN 4, score **60.0**.

## Trade-offs

- **SQLite + stdlib `sqlite3`** instead of an ORM: zero setup, simple to read, and enough for one API process. Postgres is the production plan (see DEPLOY.md).
- **FastAPI BackgroundTasks** instead of a job queue: simple, but a scan running during a restart is lost (marked FAILED). A queue + worker fixes that.
- **Polling every 1.5s** instead of WebSockets/SSE: simple and good enough at this scale.
- **Scan summaries are computed from findings on each request** instead of being stored: no duplicated data, fine for small scans.
- **No component library.** Plain CSS is enough for a 1280px desktop layout.

## Unfinished / next steps

- None of the stretch goals are done (IaC, live AWS mode with boto3/moto, CIS mapping, scan comparison, Trivy/SBOM, CSV export/API key).
- Azure NSG rule priority evaluation.
- Cancel a running scan. Retention/cleanup of old scans.
- Move to Postgres + Alembic and a real job queue for multi-instance deploys.
- Request IDs and structured JSON logs.
- An end-to-end Playwright test against the compose stack.

## Time spent (approx.)

| Part | Time |
|---|---|
| Reading the brief, plan, assumptions | 0.5 h |
| Scanner engine + 10 checks | 1 h |
| API + SQLite | 0.75 h |
| Backend tests | 0.75 h |
| Dashboard | 1.25 h |
| Dashboard tests | 0.25 h |
| Docker + compose | 0.5 h |
| CI | 0.25 h |
| README + DEPLOY.md | 0.5 h |

## Use of AI assistants

I used Claude Code (Anthropic) throughout. It helped turn the brief into a plan, scaffold the folder structure, draft the check functions, tests, Dockerfiles, CI workflow and the first drafts of this README and DEPLOY.md. I reviewed every file, checked the results against the snapshot by hand (each of the 49 findings), and made the assumption calls listed above.
