import styles from "./dashboard-metric-card.module.css";

type DashboardMetricCardProps = Readonly<{
  title: string;
  value: string;
}>;

export function DashboardMetricCard({ title, value }: DashboardMetricCardProps) {
  return (
    <article className={styles.card}>
      <p className={styles.title}>{title}</p>
      <p className={styles.value}>{value}</p>
    </article>
  );
}
