import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { loadPurchaseDetailsSummary } from "@/lib/purchase-details-data";
import { PurchaseHistoryCard } from "./purchase-history-card";

describe("PurchaseHistoryCard", () => {
  it("links simulated cards without writing purchase objects to storage", () => {
    window.sessionStorage.clear();
    render(<PurchaseHistoryCard demo amount="$29.99" href="/purchase-details/example?customerId=customer&tour=client" purchasedAt="Purchased today" status="Completed" title="Tour purchase" />);
    const link = screen.getByRole("link", { name: /Tour purchase/ });
    expect(link).toHaveAttribute("href", "/purchase-details/example?customerId=customer&tour=client");
    fireEvent.click(link);
    expect(window.sessionStorage.length).toBe(0);
  });
  it("renders purchase summary details", () => {
    const purchaseSummary = {
      headerMeta: {
        amount: "$129.99",
        orderNumber: "RAI-10001",
        status: "Completed",
      },
      productName: "Noise-canceling headphones",
      purchasedAt: "Jun 12, 2026",
      purchaseId: "40000000-0000-4000-8000-000000000001",
      purchaseType: "physical" as const,
    };

    render(
      <PurchaseHistoryCard
        amount="$129.99"
        href="/purchase-details/40000000-0000-4000-8000-000000000001"
        purchaseSummary={purchaseSummary}
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
    expect(screen.getByText("View")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Noise-canceling headphones/ }),
    ).toHaveAttribute(
      "href",
      "/purchase-details/40000000-0000-4000-8000-000000000001",
    );
    fireEvent.click(
      screen.getByRole("link", { name: /Noise-canceling headphones/ }),
    );
    expect(
      loadPurchaseDetailsSummary("40000000-0000-4000-8000-000000000001"),
    ).toEqual(purchaseSummary);
  });

  it("does not cache purchase details when no summary is provided", () => {
    render(
      <PurchaseHistoryCard
        amount="$29.99"
        href="/purchase-details/40000000-0000-4000-8000-000000000099"
        purchasedAt="Purchased Jul 01, 2026"
        status="Completed"
        title="Digital art pack"
      />,
    );

    fireEvent.click(screen.getByRole("link", { name: /Digital art pack/ }));

    expect(
      loadPurchaseDetailsSummary("40000000-0000-4000-8000-000000000099"),
    ).toBeNull();
  });
});
