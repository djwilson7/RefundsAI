import { describe, expect, it, vi } from "vitest";
import { buildDemoPurchases } from "./demo-purchases";
import { mockCustomers } from "@/components/mock-customers";

describe("deterministic tour purchases", () => {
  it("rebuilds the same independent records with a single daily reference", () => {
    const first = buildDemoPurchases(mockCustomers[0].id, "2026-07-03");
    vi.useFakeTimers();
    try {
      vi.setSystemTime(new Date("2030-01-01T00:00:00Z"));
      const next = buildDemoPurchases(mockCustomers[0].id, "2026-07-03");
      expect(next).toEqual(first);
      expect(next[0]).not.toBe(first[0]);
    } finally { vi.useRealTimers(); }
  });

  it("preserves the backend seed distribution, unique IDs, and catalog prices", () => {
    const all = mockCustomers.flatMap((customer) => buildDemoPurchases(customer.id, "2026-07-03"));
    expect(all).toHaveLength(180);
    expect(new Set(all.map((purchase) => purchase.id)).size).toBe(180);
    expect(new Set(all.map((purchase) => purchase.orderNumber)).size).toBe(180);
    expect(all.filter((purchase) => purchase.purchaseType === "physical")).toHaveLength(90);
    expect(all.filter((purchase) => purchase.purchaseType === "digital")).toHaveLength(54);
    expect(all.filter((purchase) => purchase.purchaseType === "subscription")).toHaveLength(36);
    expect(all.filter((purchase) => purchase.status === "redeemed")).toHaveLength(14);
    const first = all.find((purchase) => purchase.id.endsWith("000000000001"));
    expect(first).toMatchObject({productName: "Wireless Headphones", amountCents: 12999, orderNumber: "RAI-10001", purchasedAt: "2026-05-20T14:00:00Z"});
    expect(all.find((purchase) => purchase.id.endsWith("000000000007"))).toMatchObject({purchaseType: "digital", status: "redeemed", purchasedAt: "2026-06-14T14:06:00Z"});
    for (const customer of mockCustomers) {
      const purchases = buildDemoPurchases(customer.id);
      expect(purchases).toHaveLength(12);
      expect(purchases.map((purchase) => purchase.purchasedAt)).toEqual(purchases.map((purchase) => purchase.purchasedAt).sort().reverse());
    }
  });

  it("does not generate purchases for an unknown customer", () => {
    expect(buildDemoPurchases("unknown")).toEqual([]);
  });

  it("anchors to the current UTC day while keeping IDs and amounts stable", () => {
    vi.useFakeTimers();
    try {
      vi.setSystemTime(new Date("2026-09-30T23:59:00Z"));
      const today = buildDemoPurchases(mockCustomers[0].id);
      expect(today).toEqual(buildDemoPurchases(mockCustomers[0].id, "2026-09-30T01:00:00Z"));
      vi.setSystemTime(new Date("2026-10-01T00:01:00Z"));
      const tomorrow = buildDemoPurchases(mockCustomers[0].id);
      today.forEach((purchase, index) => {
        expect(tomorrow[index]).toEqual({...purchase, purchasedAt: new Date(Date.parse(purchase.purchasedAt) + 86_400_000).toISOString().replace(".000Z", "Z")});
      });
    } finally { vi.useRealTimers(); }
  });
});
