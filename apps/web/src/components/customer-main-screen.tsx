import { DashboardMetricCard } from "./dashboard-metric-card";
import { HomeHeaderCard } from "./home-header-card";
import {
  formatCentsAsDollars,
  formatPurchaseDate,
  formatPurchaseStatus,
  type CustomerProfile,
  type CustomerPurchase,
} from "@/lib/application-api";
import { getIdentityDisplayName } from "./mock-customers";
import { PurchaseHistoryCard } from "./purchase-history-card";
import styles from "./customer-main-screen.module.css";

type CustomerMainScreenProps = Readonly<{
  customer: CustomerProfile;
  purchases: readonly CustomerPurchase[];
}>;

export function CustomerMainScreen({
  customer,
  purchases,
}: CustomerMainScreenProps) {
  const customerName = getIdentityDisplayName(customer);
  const customerSince = formatCustomerSinceYear(customer.createdAt);
  const totalSpentCents = purchases.reduce(
    (total, purchase) => total + purchase.amountCents,
    0,
  );
  const customerMetrics = [
    { title: "Customer Since", value: customerSince },
    { title: "Items Purchased", value: purchases.length.toString() },
    { title: "Total Spent", value: formatCentsAsDollars(totalSpentCents) },
  ];

  return (
    <HomeHeaderCard
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
          Purchase History
        </h2>
        <div className={styles.purchaseGrid}>
          {purchases.map((purchase) => (
            <PurchaseHistoryCard
              amount={formatCentsAsDollars(purchase.amountCents)}
              key={purchase.id}
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
