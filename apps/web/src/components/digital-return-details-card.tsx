import styles from "./digital-return-details-card.module.css";

type DigitalReturnDetailsCardProps = Readonly<{
  invalidatedAt: string;
}>;

export function DigitalReturnDetailsCard({
  invalidatedAt,
}: DigitalReturnDetailsCardProps) {
  return (
    <section className={styles.card} aria-label="Digital return details">
      <div>
        <span
          className={styles.marker}
          role="img"
          aria-label="Code invalidated complete"
        >
          <span className={styles.completeMark} aria-hidden="true">
            ✓
          </span>
        </span>
        <p>Code Invalidated</p>
        <p>Invalidated</p>
      </div>
      <div>
        <span
          className={styles.marker}
          role="img"
          aria-label="Invalidated at complete"
        >
          <span className={styles.completeMark} aria-hidden="true">
            ✓
          </span>
        </span>
        <p>Invalidated At</p>
        <p>{invalidatedAt}</p>
      </div>
    </section>
  );
}
