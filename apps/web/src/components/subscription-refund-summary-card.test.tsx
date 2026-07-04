import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SubscriptionRefundSummaryCard } from "./subscription-refund-summary-card";

describe("SubscriptionRefundSummaryCard", () => {
  it("renders cancellation state without issued refund details", () => {
    render(
      <SubscriptionRefundSummaryCard
        autoRenewState="Off"
        cancellationStatus="Subscription Cancelled"
        daysUsed="13 days"
      />,
    );

    expect(
      screen.getByRole("region", { name: "Subscription refund summary" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Auto Renew")).toBeInTheDocument();
    expect(screen.getByText("Off")).toBeInTheDocument();
    expect(screen.getByText("Days Used")).toBeInTheDocument();
    expect(screen.getByText("13 days")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Subscription Cancelled")).toBeInTheDocument();
    expect(screen.queryByText("Cancel Date")).not.toBeInTheDocument();
  });

  it("renders issued refund amount and expected refund window", () => {
    render(
      <SubscriptionRefundSummaryCard
        autoRenewState="Off"
        cancellationStatus="Subscription Cancelled"
        cancelledAt="Jul 03, 2026"
        daysUsed="13 days"
        estimatedReleaseDateRange="Jul 08 - Jul 17"
        estimatedReleasePolicy="3-10 business days"
        refundAmount="$17.50"
      />,
    );

    expect(screen.getByText("Cancel Date")).toBeInTheDocument();
    expect(screen.getByText("Jul 03, 2026")).toBeInTheDocument();
    expect(screen.getByText("Amount")).toBeInTheDocument();
    expect(screen.getByText("$17.50")).toBeInTheDocument();
    expect(screen.getByText("Expected Refund Window")).toBeInTheDocument();
    expect(screen.getByText("3-10 business days")).toBeInTheDocument();
    expect(screen.getByText("Jul 08 - Jul 17")).toBeInTheDocument();
  });
});
