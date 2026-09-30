import purchaseSeed from "./fixtures/purchase_seed.json";
import identitySeed from "./fixtures/identity_seed.json";
import type { CustomerPurchase, PurchaseType } from "./application-api";

// Match the backend's daily UTC 14:00 anchor; generate once on the server per load.
const dayMs = 86_400_000;
const minuteMs = 60_000;

export function buildDemoPurchases(customerId: string, referenceDate = new Date().toISOString()): CustomerPurchase[] {
  const customerIds = identitySeed.user_roles
    .filter((assignment) => assignment.role_key === "customer")
    .map((assignment) => assignment.user_id);
  if (!customerIds.includes(customerId)) return [];

  const plan = purchaseSeed.purchase_plan;
  const types: PurchaseType[] = ["physical", "digital", "subscription"];
  const typePool = types.flatMap((type) => Array<PurchaseType>(plan.type_distribution[type]).fill(type));
  const reference = new Date(referenceDate);
  const anchorMs = Date.UTC(reference.getUTCFullYear(), reference.getUTCMonth(), reference.getUTCDate(), 14);
  const purchases: CustomerPurchase[] = [];
  let digitalIndex = 0;

  // Walk every customer in seed order to preserve global IDs and digital status.
  customerIds.forEach((id, customerIndex) => {
    for (let purchaseIndex = 0; purchaseIndex < plan.purchases_per_customer; purchaseIndex += 1) {
      const sequenceIndex = customerIndex * plan.purchases_per_customer + purchaseIndex;
      const type = typePool[customerIndex + purchaseIndex * customerIds.length];
      const products = purchaseSeed.products.filter((product) => product.product_type === type);
      const product = products[(customerIndex + purchaseIndex) % products.length];
      let purchasedAtMs = anchorMs - 44 * dayMs + (sequenceIndex % 45) * dayMs + sequenceIndex * minuteMs;
      let status = type === "subscription" ? "subscribed" : "completed";

      if (type === "digital") {
        purchasedAtMs = anchorMs - 19 * dayMs + (digitalIndex % 20) * dayMs + sequenceIndex * minuteMs;
        status = digitalIndex % 4 === 0 ? "redeemed" : "completed";
        digitalIndex += 1;
      }

      if (id === customerId) {
        purchases.push({
          id: `40000000-0000-4000-8000-${String(sequenceIndex + 1).padStart(12, "0")}`,
          orderNumber: `RAI-${plan.first_order_number + sequenceIndex}`,
          purchaseType: type,
          productName: product.name,
          amountCents: product.base_price_cents,
          purchasedAt: new Date(purchasedAtMs).toISOString().replace(".000Z", "Z"),
          status,
        });
      }
    }
  });

  return purchases.sort((a, b) => b.purchasedAt.localeCompare(a.purchasedAt));
}
