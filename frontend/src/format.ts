// Display helpers.

export function formatScore(score: number | null): string {
  return score === null ? "N/A" : `${score.toFixed(1)}%`;
}

/** Start time in the viewer's own time zone. */
export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

export function formatDuration(startIso: string, endIso: string | null): string {
  if (!endIso) return "—";
  const seconds = (new Date(endIso).getTime() - new Date(startIso).getTime()) / 1000;
  return `${seconds.toFixed(1)}s`;
}
