import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  DigitalPurchaseTimelineCard,
  formatDigitalTimelineDate,
  getActiveStepIndex,
} from "./digital-purchase-timeline-card";

describe("DigitalPurchaseTimelineCard", () => {
  it("renders digital purchase steps", () => {
    render(
      <DigitalPurchaseTimelineCard
        codeIssuedAt="2026-06-20T14:45:00Z"
        purchasedAt="Jun 20, 2026"
      />,
    );

    expect(
      screen.getByRole("region", { name: "Digital purchase timeline" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Purchased At")).toBeInTheDocument();
    expect(screen.getAllByText("Jun 20, 2026")).toHaveLength(2);
    expect(screen.getByText("Code Issued")).toBeInTheDocument();
  });

  it("shows pending state values when the code has not been issued", () => {
    render(
      <DigitalPurchaseTimelineCard
        codeIssuedAt={null}
        purchasedAt="Jun 20, 2026"
      />,
    );

    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("formats invalid dates defensively", () => {
    expect(formatDigitalTimelineDate("not-a-date")).toBe("Date unavailable");
  });

  it("selects the first pending step as active", () => {
    expect(
      getActiveStepIndex([
        { label: "Purchased At", state: "complete", value: "Jun 20, 2026" },
        { label: "Code Issued", state: "pending", value: "Pending" },
      ]),
    ).toBe(1);
    expect(
      getActiveStepIndex([
        { label: "Purchased At", state: "complete", value: "Jun 20, 2026" },
        { label: "Code Issued", state: "complete", value: "Jun 20, 2026" },
      ]),
    ).toBe(1);
  });
});
