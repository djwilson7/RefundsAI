import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PurchaseHistoryCard } from "./purchase-history-card";

describe("PurchaseHistoryCard", () => {
  it("renders purchase summary details", () => {
    render(
      <PurchaseHistoryCard
        amount="$129.99"
        purchasedAt="Purchased Jun 12, 2026"
        status="Completed"
        title="Noise-canceling headphones"
      />,
    );

    expect(
      screen.getByRole("heading", {
        level: 3,
        name: "Noise-canceling headphones",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("$129.99")).toBeInTheDocument();
    expect(screen.getByText("Purchased Jun 12, 2026")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });
});
