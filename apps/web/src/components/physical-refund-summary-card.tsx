import styles from "./physical-refund-summary-card.module.css";

type PhysicalRefundSummaryCardProps = Readonly<{
  estimatedReleaseDateRange: string;
  estimatedReleasePolicy: string;
  refundAmount: string;
  returnIssuedAt: string;
}>;

export function PhysicalRefundSummaryCard({
  estimatedReleaseDateRange,
  estimatedReleasePolicy,
  refundAmount,
  returnIssuedAt,
}: PhysicalRefundSummaryCardProps) {
  return (
    <section className={styles.card} aria-label="Physical refund summary">
      <div>
        <p>Return Issued</p>
        <p>{returnIssuedAt}</p>
      </div>
      <div>
        <p>Amount</p>
        <p>{refundAmount}</p>
      </div>
      <div>
        <p>Estimated Return Window</p>
        <p>
          <span>{estimatedReleasePolicy}</span>
          <span>{estimatedReleaseDateRange}</span>
        </p>
      </div>
    </section>
  );
}
