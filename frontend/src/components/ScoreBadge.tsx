import { formatScore } from "../format";

function scoreClass(score: number | null): string {
  if (score === null) return "score score-none";
  if (score >= 80) return "score score-good";
  if (score >= 50) return "score score-ok";
  return "score score-bad";
}

export default function ScoreBadge({ score }: { score: number | null }) {
  return <span className={scoreClass(score)}>{formatScore(score)}</span>;
}
