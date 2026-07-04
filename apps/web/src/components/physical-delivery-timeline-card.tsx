import styles from "./physical-delivery-timeline-card.module.css";

type PhysicalDeliveryTimelineCardProps = Readonly<{
  deliveredAt: string | null;
  purchasedAt: string;
  scheduledDeliveryAt: string | null;
}>;

type TimelineStep = Readonly<{
  label: string;
  state: "complete" | "pending";
  value: string;
}>;

export function PhysicalDeliveryTimelineCard({
  deliveredAt,
  purchasedAt,
  scheduledDeliveryAt,
}: PhysicalDeliveryTimelineCardProps) {
  const steps: readonly TimelineStep[] = [
    {
      label: "Purchased",
      state: "complete",
      value: purchasedAt,
    },
    {
      label: "Scheduled Delivery",
      state: scheduledDeliveryAt ? "complete" : "pending",
      value: scheduledDeliveryAt
        ? formatPhysicalTimelineDate(scheduledDeliveryAt)
        : "Pending",
    },
    {
      label: "Delivered",
      state: deliveredAt ? "complete" : "pending",
      value: deliveredAt ? formatPhysicalTimelineDate(deliveredAt) : "Awaiting delivery",
    },
  ];
  const activeStepIndex = getActiveStepIndex(steps);

  return (
    <section className={styles.card} aria-label="Physical delivery timeline">
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

export function formatPhysicalTimelineDate(value: string) {
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
