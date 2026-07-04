import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DashboardMetricCard } from "./dashboard-metric-card";

describe("DashboardMetricCard", () => {
  it("renders a reusable metric title and value", () => {
    render(<DashboardMetricCard title="Items Purchased" value="745" />);

    expect(screen.getByText("Items Purchased")).toBeInTheDocument();
    expect(screen.getByText("745")).toBeInTheDocument();
  });
});
