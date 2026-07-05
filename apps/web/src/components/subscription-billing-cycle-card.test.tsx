import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  calculateBillingCycleProgress,
  calculateProgressPosition,
  formatBillingCycleDate,
  SubscriptionBillingCycleCard,
} from "./subscription-billing-cycle-card";

describe("SubscriptionBillingCycleCard", () => {
  it("renders the billing cycle dates", () => {
    render(
      <SubscriptionBillingCycleCard
        currentDate="2026-07-05T00:00:00Z"
        periodEnd="2026-07-20T00:00:00Z"
        periodStart="2026-06-20T00:00:00Z"
      />,
    );

    expect(
      screen.getByRole("region", { name: "Subscription billing cycle" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Billing Start")).toBeInTheDocument();
    expect(screen.getByText("Jun 20")).toBeInTheDocument();
    expect(screen.getByText("Billing End")).toBeInTheDocument();
    expect(screen.getByText("Jul 20")).toBeInTheDocument();
    expect(screen.queryByText("Current Date")).not.toBeInTheDocument();
    expect(screen.queryByText("Jul 05")).not.toBeInTheDocument();
    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Billing cycle progress 50%" }),
    ).toBeInTheDocument();
  });

  it("renders cancelled billing cycle state from service end date", () => {
    render(
      <SubscriptionBillingCycleCard
        currentDate="2026-07-05T00:00:00Z"
        periodEnd="2026-07-20T00:00:00Z"
        periodStart="2026-06-20T00:00:00Z"
        serviceEndedAt="2026-07-03T00:00:00Z"
      />,
    );

    expect(screen.getByText("Cancelled")).toBeInTheDocument();
    expect(screen.getByText("Jul 03")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Subscription cancelled Jul 03" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Today")).not.toBeInTheDocument();
  });

  it("calculates clamped billing cycle progress", () => {
    expect(
      calculateBillingCycleProgress({
        currentDate: "2026-07-05T00:00:00Z",
        periodEnd: "2026-07-20T00:00:00Z",
        periodStart: "2026-06-20T00:00:00Z",
      }),
    ).toBe(50);
    expect(
      calculateBillingCycleProgress({
        currentDate: "2026-06-01T00:00:00Z",
        periodEnd: "2026-07-20T00:00:00Z",
        periodStart: "2026-06-20T00:00:00Z",
      }),
    ).toBe(0);
    expect(
      calculateBillingCycleProgress({
        currentDate: "2026-08-01T00:00:00Z",
        periodEnd: "2026-07-20T00:00:00Z",
        periodStart: "2026-06-20T00:00:00Z",
      }),
    ).toBe(100);
  });

  it("returns zero progress for invalid billing cycle inputs", () => {
    expect(
      calculateBillingCycleProgress({
        currentDate: "not-a-date",
        periodEnd: "2026-07-20T00:00:00Z",
        periodStart: "2026-06-20T00:00:00Z",
      }),
    ).toBe(0);
    expect(
      calculateBillingCycleProgress({
        currentDate: "2026-07-05T00:00:00Z",
        periodEnd: "not-a-date",
        periodStart: "2026-06-20T00:00:00Z",
      }),
    ).toBe(0);
    expect(
      calculateBillingCycleProgress({
        currentDate: "2026-07-05T00:00:00Z",
        periodEnd: "2026-07-20T00:00:00Z",
        periodStart: "not-a-date",
      }),
    ).toBe(0);
    expect(
      calculateBillingCycleProgress({
        currentDate: "2026-07-05T00:00:00Z",
        periodEnd: "2026-06-20T00:00:00Z",
        periodStart: "2026-06-20T00:00:00Z",
      }),
    ).toBe(0);
  });

  it("rounds progress to supported CSS positions", () => {
    expect(calculateProgressPosition(48)).toBe(50);
    expect(calculateProgressPosition(-4)).toBe(0);
    expect(calculateProgressPosition(104)).toBe(100);
  });

  it("formats invalid dates defensively", () => {
    expect(formatBillingCycleDate("not-a-date")).toBe("Date unavailable");
  });
});
