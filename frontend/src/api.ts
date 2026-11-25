// Tiny wrapper around fetch. All requests go to /api (proxied to the backend).
import type { FindingFilters, FindingsPage, Scan, ScanDetail } from "./types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, options);
  } catch {
    throw new Error("Cannot reach the API. Is the backend running?");
  }
  if (!response.ok) {
    throw new Error(`API error ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function listScans(): Promise<Scan[]> {
  return request("/scans");
}

export function getScan(id: string): Promise<ScanDetail> {
  return request(`/scans/${encodeURIComponent(id)}`);
}

export function startScan(): Promise<Scan> {
  return request("/scans", { method: "POST" });
}

export function getFindings(id: string, filters: FindingFilters, page: number): Promise<FindingsPage> {
  const params = new URLSearchParams({ page: String(page), page_size: "25" });
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  return request(`/scans/${encodeURIComponent(id)}/findings?${params}`);
}
