import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PhysicalTrackingCard } from "./physical-tracking-card";

describe("PhysicalTrackingCard", () => {
  it("renders courier and tracking number", () => {
    render(
      <PhysicalTrackingCard courier="UPS" trackingNumber="TRK-RAI-10001" />,
    );

    expect(
      screen.getByRole("region", { name: "Delivery tracking details" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Delivery Courier")).toBeInTheDocument();
    expect(screen.getByText("UPS")).toBeInTheDocument();
    expect(screen.getByText("Delivery Tracking Number")).toBeInTheDocument();
    expect(screen.getByText("TRK-RAI-10001")).toBeInTheDocument();
  });

  it("renders fallback values when tracking data is unavailable", () => {
    render(<PhysicalTrackingCard courier={null} trackingNumber={null} />);

    expect(screen.getByText("Courier unavailable")).toBeInTheDocument();
    expect(screen.getByText("Tracking unavailable")).toBeInTheDocument();
  });
});
