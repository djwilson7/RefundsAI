import identitySeed from "./fixtures/identity_seed.json";
import { buildDemoPurchases } from "./demo-purchases";
import type { CustomerPurchase } from "./application-api";
import { formatPurchaseDetailsDate } from "./purchase-details-data";

export type DemoPurchaseDetail = Readonly<{
  purchase: CustomerPurchase;
  status: string;
  facts: readonly { label: string; value: string }[];
  timeline: readonly { label: string; date: string | null; complete: boolean }[];
  policyNote: string;
}>;

// Presentation fixtures mirror seed events, without evaluating refund eligibility.
export function buildDemoPurchaseDetail(customerId: string, purchaseId: string, referenceDate: string): DemoPurchaseDetail | null {
  const purchase = buildDemoPurchases(customerId, referenceDate).find((item) => item.id === purchaseId);
  if (!purchase) return null;
  const purchasedAt = Date.parse(purchase.purchasedAt);
  const dateAfter = (days: number, minutes = 0) => new Date(purchasedAt + days * 86_400_000 + minutes * 60_000).toISOString();
  const purchasedEvent = { label: "Purchased", date: purchase.purchasedAt, complete: true };

  if (purchase.purchaseType === "digital") {
    const redeemed = purchase.status === "redeemed";
    return {
      purchase,
      status: redeemed ? "Code redeemed" : "Code ready to use",
      facts: [
        { label: "Access code", value: `DIG-${purchase.orderNumber}` },
        { label: "Code status", value: redeemed ? "Redeemed" : "Unredeemed" },
        { label: "Code delivered", value: formatPurchaseDetailsDate(dateAfter(0, 5)) },
      ],
      timeline: [purchasedEvent, { label: "Delivered", date: dateAfter(0, 5), complete: true },
        { label: "Redeemed", date: redeemed ? dateAfter(0, 60) : null, complete: redeemed }],
      policyNote: "Digital refunds require an unredeemed code and a purchase within the 15-day refund window.",
    };
  }

  if (purchase.purchaseType === "physical") {
    // The seed cycles delivery offsets and couriers across all physical orders.
    const physicalIndex = identitySeed.user_roles.filter((role) => role.role_key === "customer")
      .flatMap((role) => buildDemoPurchases(role.user_id, referenceDate))
      .filter((item) => item.purchaseType === "physical" && item.id < purchase.id).length;
    const scheduledAt = dateAfter(2 + physicalIndex % 6);
    const delivered = Date.parse(scheduledAt) <= Date.parse(referenceDate);
    return {
      purchase,
      status: delivered ? "Delivered · no return requested" : "Delivery scheduled",
      facts: [
        { label: "Courier", value: ["UPS", "FedEx", "USPS", "DHL"][physicalIndex % 4] },
        { label: "Tracking number", value: `TRK-${purchase.orderNumber}` },
        { label: "Return status", value: "Not requested" },
      ],
      timeline: [purchasedEvent, { label: delivered ? "Delivered" : "Scheduled delivery", date: scheduledAt, complete: delivered }],
      policyNote: "Physical purchases can be returned within 30 days of purchase. A refund is issued after the return is accepted by the courier.",
    };
  }

  const periodEnd = dateAfter(30);
  const periodEnded = Date.parse(periodEnd) <= Date.parse(referenceDate);
  return {
    purchase,
    status: periodEnded ? "Seeded billing period ended" : "Active billing period",
    facts: [
      { label: "Billing start", value: formatPurchaseDetailsDate(purchase.purchasedAt) },
      { label: "Billing end", value: formatPurchaseDetailsDate(periodEnd) },
      { label: "Auto-renew", value: "Enabled" },
      { label: "Cancellation", value: "Not requested" },
    ],
    timeline: [{ ...purchasedEvent, label: "Billing period started" }, { label: "Billing period ends", date: periodEnd, complete: periodEnded }],
    policyNote: "Subscriptions can receive a full refund within 48 hours of purchase. After that, refunds cover the unused portion of the active billing period. Cancellation ends access and stops automatic renewal.",
  };
}
