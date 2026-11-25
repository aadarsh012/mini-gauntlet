import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listScans, startScan } from "../api";
import ScoreBadge from "../components/ScoreBadge";
import StatusBadge from "../components/StatusBadge";
import { formatDuration, formatTime } from "../format";
import type { Scan } from "../types";

const POLL_MS = 1500;

export default function ScansPage() {
  const [scans, setScans] = useState<Scan[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const load = useCallback(async () => {
    try {
      setScans(await listScans());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  // Load once on mount.
  useEffect(() => {
    load();
  }, [load]);

  // While any scan is RUNNING, refresh every 1.5 seconds.
  const anyRunning = scans?.some((s) => s.status === "RUNNING") ?? false;
  useEffect(() => {
    if (!anyRunning) return;
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [anyRunning, load]);

  async function handleRunScan() {
    setStarting(true);
    try {
      await startScan();
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>Scans</h2>
        <button className="primary" onClick={handleRunScan} disabled={starting}>
          {starting ? "Starting…" : "Run scan"}
        </button>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {scans === null && !error && <p className="loading">Loading scans…</p>}
      {scans !== null && scans.length === 0 && (
        <p className="empty">No scans yet. Click “Run scan” to start one.</p>
      )}

      {scans !== null && scans.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>Scan</th>
              <th>Status</th>
              <th>Started</th>
              <th>Duration</th>
              <th>Score</th>
              <th>Pass / Fail / Cannot scan</th>
            </tr>
          </thead>
          <tbody>
            {scans.map((scan) => (
              <tr key={scan.id}>
                <td>
                  <Link to={`/scans/${scan.id}`}>#{scan.id}</Link>
                </td>
                <td><StatusBadge value={scan.status} /></td>
                <td>{formatTime(scan.started_at)}</td>
                <td>{formatDuration(scan.started_at, scan.finished_at)}</td>
                <td><ScoreBadge score={scan.score} /></td>
                <td>
                  {scan.counts.PASS} / {scan.counts.FAIL} / {scan.counts.CANNOT_SCAN}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
