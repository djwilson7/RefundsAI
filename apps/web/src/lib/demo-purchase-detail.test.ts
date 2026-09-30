import { describe, expect, it } from "vitest";
import { buildDemoPurchaseDetail } from "./demo-purchase-detail";
import { buildDemoPurchases } from "./demo-purchases";
import { mockCustomers } from "@/components/mock-customers";

const customerId = mockCustomers[0].id;
const referenceDate = "2026-09-30T18:00:00Z";

describe("demo purchase details", () => {
  it("only resolves purchases belonging to the selected seeded customer", () => {
    expect(buildDemoPurchaseDetail(customerId, "unknown", referenceDate)).toBeNull();
    const other = buildDemoPurchases(mockCustomers[1].id, referenceDate)[0];
    expect(buildDemoPurchaseDetail(customerId, other.id, referenceDate)).toBeNull();
  });

  it("reproduces seeded code, delivery, and billing facts for all three types", () => {
    const purchases = buildDemoPurchases(customerId, referenceDate);
    const unused = purchases.find((p) => p.purchaseType === "digital" && p.status === "completed")!;
    const unusedDetail = buildDemoPurchaseDetail(customerId, unused.id, referenceDate)!;
    expect(unusedDetail.timeline).toContainEqual({ label: "Redeemed", date: null, complete: false });
    expect(unusedDetail.timeline.some((event) => event.label === "Invalidated")).toBe(false);
    const digital = purchases.find((p) => p.purchaseType === "digital" && p.status === "redeemed")!;
    expect(buildDemoPurchaseDetail(customerId, digital.id, referenceDate)).toMatchObject({
      status: "Code redeemed", facts: expect.arrayContaining([{ label: "Access code", value: `DIG-${digital.orderNumber}` }]),
      timeline: expect.arrayContaining([{ label: "Redeemed", date: new Date(Date.parse(digital.purchasedAt) + 3_600_000).toISOString(), complete: true }]),
    });
    const physical = purchases.find((p) => p.id.endsWith("000000000001"))!;
    expect(buildDemoPurchaseDetail(customerId, physical.id, referenceDate)).toMatchObject({
      status: "Delivered · no return requested", facts: expect.arrayContaining([{ label: "Courier", value: "UPS" }]),
      timeline: expect.arrayContaining([{ label: "Delivered", date: new Date(Date.parse(physical.purchasedAt) + 2 * 86_400_000).toISOString(), complete: true }]),
    });
    const subscription = purchases.find((p) => p.purchaseType === "subscription")!;
    expect(buildDemoPurchaseDetail(customerId, subscription.id, referenceDate)).toMatchObject({
      timeline: expect.arrayContaining([{ label: "Billing period ends", date: new Date(Date.parse(subscription.purchasedAt) + 30 * 86_400_000).toISOString(), complete: true }]),
    });
  });
});
