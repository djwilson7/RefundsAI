import { AppCard } from "./app-card";
import styles from "./admin-home-page.module.css";

export function AdminHomePage() {
  return (
    <main className={styles.page}>
      <AppCard className={styles.content}>
        <p className={styles.eyebrow}>Admin dashboard</p>
        <h1 className={styles.heading}>Admin home</h1>
        <p className={styles.summary}>
          This placeholder is ready for operational support workflows.
        </p>
      </AppCard>
    </main>
  );
}
