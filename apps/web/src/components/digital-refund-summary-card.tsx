import styles from "./digital-refund-summary-card.module.css";

type DigitalRefundSummaryCardProps = Readonly<{
  estimatedReleaseDateRange: string;
  estimatedReleasePolicy: string;
  refundAmount: string;
  refundIssuedAt: string;
}>;

export function DigitalRefundSummaryCard({
  estimatedReleaseDateRange,
  estimatedReleasePolicy,
  refundAmount,
  refundIssuedAt,
}: DigitalRefundSummaryCardProps) {
  return (
    <section className={styles.card} aria-label="Digital refund summary">
      <div>
        <p>Date Issued</p>
        <p>{refundIssuedAt}</p>
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
