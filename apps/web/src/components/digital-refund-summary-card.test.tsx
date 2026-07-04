import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DigitalRefundSummaryCard } from "./digital-refund-summary-card";

describe("DigitalRefundSummaryCard", () => {
  it("renders issued refund amount and estimated release window", () => {
    render(
      <DigitalRefundSummaryCard
        estimatedReleaseDateRange="Jul 08 - Jul 17"
        estimatedReleasePolicy="3-10 business days"
        refundAmount="$59.00"
        refundIssuedAt="Jul 04, 2026"
      />,
    );

    expect(
      screen.getByRole("region", { name: "Digital refund summary" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Date Issued")).toBeInTheDocument();
    expect(screen.getByText("Jul 04, 2026")).toBeInTheDocument();
    expect(screen.getByText("Amount")).toBeInTheDocument();
    expect(screen.getByText("$59.00")).toBeInTheDocument();
    expect(screen.getByText("Estimated Return Window")).toBeInTheDocument();
    expect(screen.getByText("3-10 business days")).toBeInTheDocument();
    expect(screen.getByText("Jul 08 - Jul 17")).toBeInTheDocument();
  });
});
