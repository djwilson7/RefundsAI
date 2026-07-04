import styles from "./subscription-billing-cycle-card.module.css";

type SubscriptionBillingCycleCardProps = Readonly<{
  currentDate: string;
  periodEnd: string;
  periodStart: string;
}>;

export function SubscriptionBillingCycleCard({
  currentDate,
  periodEnd,
  periodStart,
}: SubscriptionBillingCycleCardProps) {
  const progress = calculateBillingCycleProgress({
    currentDate,
    periodEnd,
    periodStart,
  });
  const progressPosition = calculateProgressPosition(progress);
  const progressPositionClassName = progressPositionClassNames[progressPosition];

  return (
    <section
      className={styles.card}
      aria-label="Subscription billing cycle"
    >
      <div className={styles.header}>
        <div>
          <p>Billing Start</p>
          <p>{formatBillingCycleDate(periodStart)}</p>
        </div>
        <div>
          <p>Billing End</p>
          <p>{formatBillingCycleDate(periodEnd)}</p>
        </div>
      </div>
      <div
        className={styles.progress}
        role="img"
        aria-label={`Billing cycle progress ${progress}%`}
      >
        <div className={styles.track}>
          <div
            className={`${styles.fill} ${styles[progressPositionClassName]}`}
          />
        </div>
        <div
          className={`${styles.markerGroup} ${styles[progressPositionClassName]}`}
        >
          <span className={styles.marker} aria-hidden="true" />
          <span className={styles.todayLabel}>Today</span>
        </div>
      </div>
    </section>
  );
}

export function calculateBillingCycleProgress({
  currentDate,
  periodEnd,
  periodStart,
}: SubscriptionBillingCycleCardProps) {
  const startTime = new Date(periodStart).getTime();
  const endTime = new Date(periodEnd).getTime();
  const currentTime = new Date(currentDate).getTime();

  if (
    Number.isNaN(startTime) ||
    Number.isNaN(endTime) ||
    Number.isNaN(currentTime) ||
    endTime <= startTime
  ) {
    return 0;
  }

  const progress = ((currentTime - startTime) / (endTime - startTime)) * 100;

  return Math.min(100, Math.max(0, Math.round(progress)));
}

export function calculateProgressPosition(progress: number): ProgressPosition {
  const progressPosition = Math.min(
    100,
    Math.max(0, Math.round(progress / 5) * 5),
  );

  return progressPosition as ProgressPosition;
}

export function formatBillingCycleDate(value: string) {
  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Date unavailable";
  }

  return new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
  }).format(parsedDate);
}

const progressPositionClassNames = {
  0: "position0",
  5: "position5",
  10: "position10",
  15: "position15",
  20: "position20",
  25: "position25",
  30: "position30",
  35: "position35",
  40: "position40",
  45: "position45",
  50: "position50",
  55: "position55",
  60: "position60",
  65: "position65",
  70: "position70",
  75: "position75",
  80: "position80",
  85: "position85",
  90: "position90",
  95: "position95",
  100: "position100",
} as const;

type ProgressPosition = keyof typeof progressPositionClassNames;
