import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getFindings, getScan } from "../api";
import CountCards from "../components/CountCards";
import Filters from "../components/Filters";
import FindingsTable from "../components/FindingsTable";
import Pagination from "../components/Pagination";
import ScoreBadge from "../components/ScoreBadge";
import StatusBadge from "../components/StatusBadge";
import { formatDuration, formatTime } from "../format";
import type { FindingFilters, FindingsPage, ScanDetail } from "../types";

const POLL_MS = 1500;
const NO_FILTERS: FindingFilters = { status: "", severity: "", provider: "", account_id: "" };

export default function ScanPage() {
  const { id = "" } = useParams();
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);

  const [filters, setFilters] = useState<FindingFilters>(NO_FILTERS);
  const [page, setPage] = useState(1);
  const [findings, setFindings] = useState<FindingsPage | null>(null);
  const [findingsError, setFindingsError] = useState<string | null>(null);

  const loadScan = useCallback(async () => {
    try {
      setScan(await getScan(id));
      setScanError(null);
    } catch (e) {
      setScanError((e as Error).message);
    }
  }, [id]);

  useEffect(() => {
    loadScan();
  }, [loadScan]);

  // Keep polling while the scan is still running.
  const running = scan?.status === "RUNNING";
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(loadScan, POLL_MS);
    return () => clearInterval(timer);
  }, [running, loadScan]);

  // Reload findings when the filters, page or scan status change.
  const scanStatus = scan?.status;
  useEffect(() => {
    if (!scanStatus) return;
    let cancelled = false; // ignore answers to requests we no longer care about
    getFindings(id, filters, page)
      .then((result) => {
        if (!cancelled) {
          setFindings(result);
          setFindingsError(null);
        }
      })
      .catch((e: Error) => {
        if (!cancelled) setFindingsError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [id, filters, page, scanStatus]);

  function changeFilters(next: FindingFilters) {
    setFilters(next);
    setPage(1);
  }

  if (scanError && !scan) {
    return (
      <div>
        <Link to="/">← All scans</Link>
        <p className="error" role="alert">{scanError}</p>
      </div>
    );
  }
  if (!scan) return <p className="loading">Loading scan…</p>;

  return (
    <div>
      <Link to="/">← All scans</Link>
      <div className="page-header">
        <h2>
          Scan #{scan.id} <StatusBadge value={scan.status} />
        </h2>
        <div className="big-score">
          Score <ScoreBadge score={scan.score} />
        </div>
      </div>
      <p className="muted">
        Started {formatTime(scan.started_at)} · Duration {formatDuration(scan.started_at, scan.finished_at)}
      </p>
      {scanError && <p className="error" role="alert">{scanError}</p>}
      {scan.status === "FAILED" && <p className="error">Scan failed: {scan.error}</p>}
      {running && <p className="loading">Scan in progress…</p>}

      <div className="summary">
        <CountCards title="Findings by status" counts={scan.counts} />
        <CountCards title="Failures by severity" counts={scan.fail_counts_by_severity} />
        <section className="panel">
          <h3>Score per account</h3>
          <table className="table compact">
            <tbody>
              {scan.account_scores.map((a) => (
                <tr key={a.account_id}>
                  <td className="mono">{a.account_id}</td>
                  <td><ScoreBadge score={a.score} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>

      <h3>Findings</h3>
      <Filters filters={filters} accountIds={scan.account_ids} onChange={changeFilters} />
      {findingsError && <p className="error" role="alert">{findingsError}</p>}
      {!findings && !findingsError && <p className="loading">Loading findings…</p>}
      {findings && (
        <>
          <FindingsTable findings={findings.items} />
          <Pagination page={page} pageSize={findings.page_size} total={findings.total} onPage={setPage} />
        </>
      )}
    </div>
  );
}
