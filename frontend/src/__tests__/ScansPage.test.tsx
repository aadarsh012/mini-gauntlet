import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ScansPage from "../pages/ScansPage";

function renderPage() {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ScansPage />
    </MemoryRouter>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("ScansPage", () => {
  it("shows an error when the API is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent(/cannot reach the api/i);
  });

  it("shows an empty state when there are no scans", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]")));
    renderPage();
    expect(await screen.findByText(/no scans yet/i)).toBeInTheDocument();
  });

  it("lists scans with their score", async () => {
    const scan = {
      id: 7,
      status: "COMPLETED",
      started_at: "2026-10-01T00:00:00+00:00",
      finished_at: "2026-10-01T00:00:03+00:00",
      account_ids: [],
      error: null,
      score: null,
      counts: { PASS: 0, FAIL: 0, CANNOT_SCAN: 2 },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([scan]))));
    renderPage();
    expect(await screen.findByText("#7")).toBeInTheDocument();
    expect(screen.getByText("N/A")).toBeInTheDocument();
    expect(screen.getByText("3.0s")).toBeInTheDocument();
  });
});
