import { AppCard } from "./app-card";
import { getIdentityDisplayName, type MockCustomer } from "./mock-customers";
import styles from "./customer-main-screen.module.css";

type CustomerMainScreenProps = Readonly<{
  customer: MockCustomer;
}>;

export function CustomerMainScreen({ customer }: CustomerMainScreenProps) {
  const customerName = getIdentityDisplayName(customer);

  return (
    <main className={styles.page}>
      <AppCard className={styles.content}>
        <p className={styles.eyebrow}>Customer portal</p>
        <h1 className={styles.heading}>Main screen for {customerName}</h1>
        <p className={styles.summary}>
          This placeholder is ready for the customer purchase and support views.
        </p>
      </AppCard>
    </main>
  );
}
