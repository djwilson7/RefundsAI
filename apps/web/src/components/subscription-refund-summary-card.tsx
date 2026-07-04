import styles from "./subscription-refund-summary-card.module.css";

type SubscriptionRefundSummaryCardProps = Readonly<{
  autoRenewState: string;
  cancellationStatus: string;
  cancelledAt?: string | null;
  daysUsed: string;
  estimatedReleaseDateRange?: string | null;
  estimatedReleasePolicy?: string | null;
  refundAmount?: string | null;
}>;

export function SubscriptionRefundSummaryCard({
  autoRenewState,
  cancellationStatus,
  cancelledAt,
  daysUsed,
  estimatedReleaseDateRange,
  estimatedReleasePolicy,
  refundAmount,
}: SubscriptionRefundSummaryCardProps) {
  const hasIssuedRefundSummary = Boolean(
    cancelledAt && refundAmount && estimatedReleaseDateRange && estimatedReleasePolicy,
  );

  return (
    <section className={styles.card} aria-label="Subscription refund summary">
      <div className={styles.row}>
        <div>
          <p>Auto Renew</p>
          <p>{autoRenewState}</p>
        </div>
        <div>
          <p>Days Used</p>
          <p>{daysUsed}</p>
        </div>
        <div>
          <p>Status</p>
          <p>{cancellationStatus}</p>
        </div>
      </div>
      {hasIssuedRefundSummary ? (
        <div className={styles.row}>
          <div>
            <p>Cancel Date</p>
            <p>{cancelledAt}</p>
          </div>
          <div>
            <p>Amount</p>
            <p>{refundAmount}</p>
          </div>
          <div>
            <p>Expected Refund Window</p>
            <p>
              <span>{estimatedReleasePolicy}</span>
              <span>{estimatedReleaseDateRange}</span>
            </p>
          </div>
        </div>
      ) : null}
    </section>
  );
}
