import styles from "./purchase-history-card.module.css";

type PurchaseHistoryCardProps = Readonly<{
  amount: string;
  purchasedAt: string;
  status: string;
  title: string;
}>;

export function PurchaseHistoryCard({
  amount,
  purchasedAt,
  status,
  title,
}: PurchaseHistoryCardProps) {
  return (
    <article className={styles.card}>
      <div className={styles.header}>
        <h3 className={styles.title}>{title}</h3>
        <p className={styles.amount}>{amount}</p>
      </div>

      <div className={styles.details}>
        <span>{purchasedAt}</span>
        <span className={styles.status}>{status}</span>
      </div>
    </article>
  );
}
