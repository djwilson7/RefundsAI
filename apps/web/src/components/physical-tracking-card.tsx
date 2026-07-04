import styles from "./physical-tracking-card.module.css";

type PhysicalTrackingCardProps = Readonly<{
  courier: string | null;
  trackingNumber: string | null;
}>;

export function PhysicalTrackingCard({
  courier,
  trackingNumber,
}: PhysicalTrackingCardProps) {
  return (
    <section className={styles.card} aria-label="Delivery tracking details">
      <div>
        <p>Delivery Courier</p>
        <p>{courier ?? "Courier unavailable"}</p>
      </div>
      <div>
        <p>Delivery Tracking Number</p>
        <p>{trackingNumber ?? "Tracking unavailable"}</p>
      </div>
    </section>
  );
}
