import { render, screen } from "@testing-library/react";
import FindingsTable from "../components/FindingsTable";
import type { Finding } from "../types";

const XSS = "<img src=x onerror=alert('untrusted-input')> temporary rule";

const finding: Finding = {
  id: 1,
  scan_id: 1,
  check_id: "GCP-VPC-01",
  title: "Firewall rule doesn't expose SSH or RDP to the internet",
  provider: "gcp",
  account_id: "example-corp-gcp",
  region: "global",
  resource_id: "allow-rdp-anywhere",
  status: "FAIL",
  severity: "CRITICAL",
  details: XSS,
};

describe("FindingsTable", () => {
  it("renders untrusted strings as plain text, never as HTML", () => {
    const { container } = render(<FindingsTable findings={[finding]} />);
    expect(screen.getByText(XSS)).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
  });

  it("shows each finding's fields", () => {
    render(<FindingsTable findings={[finding]} />);
    expect(screen.getByText("GCP-VPC-01")).toBeInTheDocument();
    expect(screen.getByText("allow-rdp-anywhere")).toBeInTheDocument();
    expect(screen.getByText("CRITICAL")).toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(<FindingsTable findings={[]} />);
    expect(screen.getByText(/no findings/i)).toBeInTheDocument();
  });
});
