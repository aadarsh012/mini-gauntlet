import type { Finding } from "../types";
import StatusBadge from "./StatusBadge";

// Every value here comes from the customer's cloud, so it is rendered as plain
// text through JSX (React escapes it). Never use dangerouslySetInnerHTML.
export default function FindingsTable({ findings }: { findings: Finding[] }) {
  if (findings.length === 0) {
    return <p className="empty">No findings match these filters.</p>;
  }
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Status</th>
          <th>Severity</th>
          <th>Check</th>
          <th>Provider</th>
          <th>Account</th>
          <th>Region</th>
          <th>Resource</th>
          <th>Details</th>
        </tr>
      </thead>
      <tbody>
        {findings.map((f) => (
          <tr key={f.id}>
            <td><StatusBadge value={f.status} /></td>
            <td><StatusBadge value={f.severity} /></td>
            <td title={f.title}>{f.check_id}</td>
            <td>{f.provider}</td>
            <td className="mono">{f.account_id}</td>
            <td>{f.region ?? "—"}</td>
            <td className="mono">{f.resource_id ?? "—"}</td>
            <td className="details">{f.details}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
