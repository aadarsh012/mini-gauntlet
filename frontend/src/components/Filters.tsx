import type { FindingFilters } from "../types";
import { FINDING_STATUSES, PROVIDERS, SEVERITIES } from "../types";

interface Props {
  filters: FindingFilters;
  accountIds: string[];
  onChange: (filters: FindingFilters) => void;
}

export default function Filters({ filters, accountIds, onChange }: Props) {
  const options: Record<keyof FindingFilters, string[]> = {
    status: FINDING_STATUSES,
    severity: SEVERITIES,
    provider: PROVIDERS,
    account_id: accountIds,
  };

  return (
    <div className="filters">
      {(Object.keys(options) as (keyof FindingFilters)[]).map((key) => (
        <label key={key}>
          {key.replace("_", " ")}
          <select value={filters[key]} onChange={(e) => onChange({ ...filters, [key]: e.target.value })}>
            <option value="">All</option>
            {options[key].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      ))}
    </div>
  );
}
