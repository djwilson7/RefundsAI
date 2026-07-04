import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  formatPhysicalTimelineDate,
  getActiveStepIndex,
  PhysicalDeliveryTimelineCard,
} from "./physical-delivery-timeline-card";

describe("PhysicalDeliveryTimelineCard", () => {
  it("renders physical delivery steps", () => {
    render(
      <PhysicalDeliveryTimelineCard
        deliveredAt={null}
        purchasedAt="Jun 20, 2026"
        scheduledDeliveryAt="2026-06-22T14:30:00Z"
      />,
    );

    expect(
      screen.getByRole("region", { name: "Physical delivery timeline" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Purchased")).toBeInTheDocument();
    expect(screen.getByText("Jun 20, 2026")).toBeInTheDocument();
    expect(screen.getByText("Scheduled Delivery")).toBeInTheDocument();
    expect(screen.getByText("Jun 22, 2026")).toBeInTheDocument();
    expect(screen.getByText("Delivered")).toBeInTheDocument();
    expect(screen.getByText("Awaiting delivery")).toBeInTheDocument();
  });

  it("shows delivered date when the purchase has arrived", () => {
    render(
      <PhysicalDeliveryTimelineCard
        deliveredAt="2026-06-22T14:30:00Z"
        purchasedAt="Jun 20, 2026"
        scheduledDeliveryAt="2026-06-22T14:30:00Z"
      />,
    );

    expect(screen.getByText("Delivered")).toBeInTheDocument();
    expect(screen.getAllByText("Jun 22, 2026")).toHaveLength(2);
  });

  it("selects the first pending delivery step as active", () => {
    expect(
      getActiveStepIndex([
        { label: "Purchased", state: "complete", value: "Jun 20, 2026" },
        { label: "Scheduled Delivery", state: "pending", value: "Pending" },
        { label: "Delivered", state: "pending", value: "Awaiting delivery" },
      ]),
    ).toBe(1);
    expect(
      getActiveStepIndex([
        { label: "Purchased", state: "complete", value: "Jun 20, 2026" },
        {
          label: "Scheduled Delivery",
          state: "complete",
          value: "Jun 22, 2026",
        },
        { label: "Delivered", state: "complete", value: "Jun 22, 2026" },
      ]),
    ).toBe(2);
  });

  it("formats invalid dates defensively", () => {
    expect(formatPhysicalTimelineDate("not-a-date")).toBe("Date unavailable");
  });
});
