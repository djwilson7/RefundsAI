import { DashboardMetricCard } from "./dashboard-metric-card";
import { HelpTriggerButton } from "./help-trigger-button";
import { HomeHeaderCard } from "./home-header-card";
import {
  formatCentsAsDollars,
  formatPurchaseDate,
  formatPurchaseStatus,
  type CustomerProfile,
  type CustomerPurchase,
} from "@/lib/application-api";
import {
  buildPurchaseDetailsHref,
  buildPurchaseDetailsSummary,
} from "@/lib/purchase-details-data";
import { getIdentityDisplayName } from "./mock-customers";
import { PurchaseHistoryCard } from "./purchase-history-card";
import styles from "./customer-main-screen.module.css";

type CustomerMainScreenProps = Readonly<{
  customer: CustomerProfile;
  purchases: readonly CustomerPurchase[];
  demo?: boolean;
}>;

export function CustomerMainScreen({
  customer,
  purchases,
  demo = false,
}: CustomerMainScreenProps) {
  const customerName = getIdentityDisplayName(customer);
  const customerSince = formatCustomerSinceYear(customer.createdAt);
  const aggregatePurchases = purchases.filter(isPurchaseAggregateEligible);
  const totalSpentCents = aggregatePurchases.reduce(
    (total, purchase) => total + purchase.amountCents,
    0,
  );
  const customerMetrics = [
    { title: "Customer Since", value: customerSince },
    { title: "Items Purchased", value: aggregatePurchases.length.toString() },
    { title: "Total Spent", value: formatCentsAsDollars(totalSpentCents) },
  ];

  return (
    <HomeHeaderCard
      productBanner
      customerId={customer.id}
      helpAction={<HelpTriggerButton inline />}
      eyebrow="Welcome"
      heading={customerName}
      summary="Summary Dashboard"
    >
      <section className={styles.metrics} aria-label="Customer summary metrics">
        {customerMetrics.map((metric) => (
          <DashboardMetricCard
            key={metric.title}
            title={metric.title}
            value={metric.value}
          />
        ))}
      </section>

      <section
        className={styles.purchaseHistory}
        aria-labelledby="purchase-history-title"
      >
        <h2 className={styles.sectionTitle} id="purchase-history-title">
          {demo ? "Simulated Purchase History" : "Purchase History"}
        </h2>
        <div className={styles.purchaseGrid}>
          {purchases.map((purchase) => (
            <PurchaseHistoryCard
              demo={demo}
              amount={formatCentsAsDollars(purchase.amountCents)}
              href={demo ? `${buildPurchaseDetailsHref(purchase.id)}?customerId=${customer.id}&tour=client` : buildPurchaseDetailsHref(purchase.id)}
              key={purchase.id}
              purchaseSummary={buildPurchaseDetailsSummary(purchase)}
              purchasedAt={formatPurchaseDate(purchase.purchasedAt)}
              status={formatPurchaseStatus(purchase.status)}
              title={purchase.productName}
            />
          ))}
        </div>
      </section>
    </HomeHeaderCard>
  );
}

export function formatCustomerSinceYear(createdAt: string) {
  const parsedDate = new Date(createdAt);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Unknown";
  }

  return parsedDate.getUTCFullYear().toString();
}

export function isPurchaseAggregateEligible(purchase: CustomerPurchase) {
  return purchase.status !== "refunded";
}
