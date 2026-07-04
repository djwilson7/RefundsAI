import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PhysicalRefundSummaryCard } from "./physical-refund-summary-card";

describe("PhysicalRefundSummaryCard", () => {
  it("renders issued refund amount and estimated release window", () => {
    render(
      <PhysicalRefundSummaryCard
        estimatedReleaseDateRange="Jul 08 - Jul 17"
        estimatedReleasePolicy="3-10 business days"
        refundAmount="$9.99"
        returnIssuedAt="Jul 04, 2026"
      />,
    );

    expect(
      screen.getByRole("region", { name: "Physical refund summary" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Return Issued")).toBeInTheDocument();
    expect(screen.getByText("Jul 04, 2026")).toBeInTheDocument();
    expect(screen.getByText("Amount")).toBeInTheDocument();
    expect(screen.getByText("$9.99")).toBeInTheDocument();
    expect(screen.getByText("Estimated Return Window")).toBeInTheDocument();
    expect(screen.getByText("3-10 business days")).toBeInTheDocument();
    expect(screen.getByText("Jul 08 - Jul 17")).toBeInTheDocument();
  });
});
