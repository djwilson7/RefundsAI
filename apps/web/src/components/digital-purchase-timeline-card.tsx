import styles from "./digital-purchase-timeline-card.module.css";

type DigitalPurchaseTimelineCardProps = Readonly<{
  codeIssuedAt: string | null;
  purchasedAt: string;
}>;

type TimelineStep = Readonly<{
  label: string;
  state: "complete" | "pending";
  value: string;
}>;

export function DigitalPurchaseTimelineCard({
  codeIssuedAt,
  purchasedAt,
}: DigitalPurchaseTimelineCardProps) {
  const steps: readonly TimelineStep[] = [
    {
      label: "Purchased At",
      state: "complete",
      value: purchasedAt,
    },
    {
      label: "Code Issued",
      state: codeIssuedAt ? "complete" : "pending",
      value: codeIssuedAt ? formatDigitalTimelineDate(codeIssuedAt) : "Pending",
    },
  ];
  const activeStepIndex = getActiveStepIndex(steps);

  return (
    <section className={styles.card} aria-label="Digital purchase timeline">
      <ol className={styles.steps}>
        {steps.map((step, index) => (
          <li className={styles.step} key={step.label}>
            <span className={styles.marker} aria-hidden="true">
              {step.state === "complete" ? (
                <span className={styles.completeMark}>✓</span>
              ) : (
                <span
                  className={
                    index === activeStepIndex
                      ? styles.activeDot
                      : styles.pendingDot
                  }
                />
              )}
            </span>
            <p>{step.label}</p>
            <p>{step.value}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function getActiveStepIndex(steps: readonly TimelineStep[]) {
  const firstPendingIndex = steps.findIndex((step) => step.state === "pending");

  if (firstPendingIndex >= 0) {
    return firstPendingIndex;
  }

  return steps.length - 1;
}

export function formatDigitalTimelineDate(value: string) {
  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Date unavailable";
  }

  return new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
    year: "numeric",
  }).format(parsedDate);
}
