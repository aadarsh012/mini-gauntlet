// A coloured pill for a scan status, finding status or severity.
export default function StatusBadge({ value }: { value: string }) {
  return <span className={`badge badge-${value.toLowerCase()}`}>{value}</span>;
}
