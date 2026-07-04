import { DashboardMetricCard } from "./dashboard-metric-card";
import { HomeHeaderCard } from "./home-header-card";
import { getIdentityDisplayName, type MockCustomer } from "./mock-customers";
import { PurchaseHistoryCard } from "./purchase-history-card";
import styles from "./customer-main-screen.module.css";

type CustomerMainScreenProps = Readonly<{
  customer: MockCustomer;
}>;

const customerMetrics = [
  { title: "Customer Since", value: "1992" },
  { title: "Items Purchased", value: "745" },
  { title: "Total Spent", value: "14,254.35" },
] as const;

const placeholderPurchases = [
  {
    amount: "$129.99",
    purchasedAt: "Purchased Jun 12, 2026",
    status: "Completed",
    title: "Noise-canceling headphones",
  },
  {
    amount: "$59.00",
    purchasedAt: "Purchased Jun 03, 2026",
    status: "Redeemed",
    title: "Design asset bundle",
  },
  {
    amount: "$24.99",
    purchasedAt: "Purchased May 28, 2026",
    status: "Subscribed",
    title: "Productivity Pro monthly",
  },
] as const;

export function CustomerMainScreen({ customer }: CustomerMainScreenProps) {
  const customerName = getIdentityDisplayName(customer);

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
          {placeholderPurchases.map((purchase) => (
            <PurchaseHistoryCard
              amount={purchase.amount}
              key={purchase.title}
              purchasedAt={purchase.purchasedAt}
              status={purchase.status}
              title={purchase.title}
            />
          ))}
        </div>
      </section>
    </HomeHeaderCard>
  );
}
