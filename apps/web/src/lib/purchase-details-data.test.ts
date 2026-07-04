import { describe, expect, it, vi } from "vitest";
import {
  buildFallbackPurchaseDetailsSummary,
  formatPurchaseDetailsDate,
  buildPurchaseDetailsHref,
  buildPurchaseDetailsSummary,
  loadPurchaseDetailsSummary,
  parsePurchaseDetailsSummary,
  savePurchaseDetailsSummary,
} from "./purchase-details-data";

const purchase = {
  id: "40000000-0000-4000-8000-000000000001",
  orderNumber: "RAI-10001",
  purchaseType: "physical" as const,
  productName: "Wireless Headphones",
  amountCents: 12999,
  purchasedAt: "2026-06-20T14:30:00Z",
  status: "refund_pending",
};

describe("purchase details data", () => {
  it("builds a dedicated details summary object from a purchase", () => {
    expect(buildPurchaseDetailsSummary(purchase)).toEqual({
      headerMeta: {
        amount: "$129.99",
        orderNumber: "RAI-10001",
        status: "Refund Pending",
      },
      productName: "Wireless Headphones",
      purchasedAt: "Jun 20, 2026",
      purchaseId: "40000000-0000-4000-8000-000000000001",
      purchaseType: "physical",
    });
    expect(buildPurchaseDetailsHref(purchase.id)).toBe(
      "/purchase-details/40000000-0000-4000-8000-000000000001",
    );
  });

  it("stores and loads a purchase details summary by purchase id", () => {
    const summary = buildPurchaseDetailsSummary(purchase);
    savePurchaseDetailsSummary(summary);

    expect(loadPurchaseDetailsSummary(purchase.id)).toEqual(summary);
  });

  it("falls back when stored summary data is missing or invalid", () => {
    const purchaseId = "40000000-0000-4000-8000-000000000404";

    expect(buildFallbackPurchaseDetailsSummary(purchaseId)).toEqual({
      headerMeta: {
        amount: "Amount unavailable",
        orderNumber: "Order unavailable",
        status: "Status unavailable",
      },
      productName: "Purchase details unavailable",
      purchasedAt: "Purchase date unavailable",
      purchaseId,
      purchaseType: "physical",
    });
    expect(parsePurchaseDetailsSummary("not-json", purchaseId)).toBeNull();
    expect(
      parsePurchaseDetailsSummary(
        JSON.stringify({ purchaseId, purchaseType: "unknown" }),
        purchaseId,
      ),
    ).toBeNull();
  });

  it("does not access session storage during server rendering", () => {
    const originalWindow = globalThis.window;
    vi.stubGlobal("window", undefined);

    expect(loadPurchaseDetailsSummary(purchase.id)).toBeNull();
    expect(() =>
      savePurchaseDetailsSummary(buildPurchaseDetailsSummary(purchase)),
    ).not.toThrow();

    vi.stubGlobal("window", originalWindow);
  });

  it("formats purchase dates for details metadata without action copy", () => {
    expect(formatPurchaseDetailsDate("2026-06-20T14:30:00Z")).toBe(
      "Jun 20, 2026",
    );
    expect(formatPurchaseDetailsDate("not-a-date")).toBe(
      "Purchase date unavailable",
    );
  });
});
