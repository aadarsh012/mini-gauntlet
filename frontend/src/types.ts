// Shapes returned by the API.

export type ScanStatus = "RUNNING" | "COMPLETED" | "FAILED";
export type FindingStatus = "PASS" | "FAIL" | "CANNOT_SCAN";
export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export const FINDING_STATUSES: FindingStatus[] = ["FAIL", "CANNOT_SCAN", "PASS"];
export const SEVERITIES: Severity[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
export const PROVIDERS = ["aws", "azure", "gcp"];

export interface Scan {
  id: number;
  status: ScanStatus;
  started_at: string;
  finished_at: string | null;
  account_ids: string[];
  error: string | null;
  score: number | null;
  counts: Record<FindingStatus, number>;
}

export interface ScanDetail extends Scan {
  fail_counts_by_severity: Record<Severity, number>;
  account_scores: { account_id: string; score: number | null }[];
}

export interface Finding {
  id: number;
  scan_id: number;
  check_id: string;
  title: string;
  provider: string;
  account_id: string;
  region: string | null;
  resource_id: string | null;
  status: FindingStatus;
  severity: Severity;
  details: string;
}

export interface FindingsPage {
  items: Finding[];
  total: number;
  page: number;
  page_size: number;
}

export interface FindingFilters {
  status: string;
  severity: string;
  provider: string;
  account_id: string;
}
