import { render, screen } from "@testing-library/react";
import ScoreBadge from "../components/ScoreBadge";

describe("ScoreBadge", () => {
  it("shows N/A when the score is null", () => {
    render(<ScoreBadge score={null} />);
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });

  it("shows the score with one decimal", () => {
    render(<ScoreBadge score={57.1} />);
    expect(screen.getByText("57.1%")).toBeInTheDocument();
  });
});
