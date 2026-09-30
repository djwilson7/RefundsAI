import Link from "next/link";
import { HomeHeaderCard } from "./home-header-card";
import { HelpTriggerButton } from "./help-trigger-button";
import { ArrowRightIcon } from "./icons";
import { getIdentityDisplayName } from "./mock-customers";
import { formatCentsAsDollars, type CustomerProfile } from "@/lib/application-api";
import { formatPurchaseDetailsDate } from "@/lib/purchase-details-data";
import type { DemoPurchaseDetail } from "@/lib/demo-purchase-detail";
import styles from "./tour-purchase-details.module.css";

export function TourPurchaseDetails({ customer, detail }: { customer: CustomerProfile; detail: DemoPurchaseDetail }) {
  const { purchase } = detail;
  return (
    <HomeHeaderCard productBanner customerId={customer.id} heading={getIdentityDisplayName(customer)} eyebrow="" summary="" helpAction={<HelpTriggerButton inline />}>
      <div className={`${styles.details} ${styles[purchase.purchaseType]}`}>
        <div className={styles.topbar}>
          <Link className={styles.back} href={`/user-home?customerId=${customer.id}&tour=client`} aria-label="Back to purchase history" title="Back to purchase history"><ArrowRightIcon /></Link>
          <p className={styles.simulatedLabel}>Simulated Purchase</p>
        </div>
        <section className={styles.card} aria-labelledby="purchase-title">
          <div className={styles.headingRow}>
            <div className={styles.heroDetails}>
              <p className={styles.eyebrow}>{purchase.purchaseType} purchase</p>
              <h1 id="purchase-title">{purchase.productName}</h1>
              <div className={styles.meta}><span>{purchase.orderNumber}</span><span>Purchased {formatPurchaseDetailsDate(purchase.purchasedAt)}</span></div>
            </div>
            <p className={styles.amount}>{formatCentsAsDollars(purchase.amountCents)}</p>
          </div>
        </section>
        <div className={styles.grid}>
          <section className={styles.card} aria-labelledby="current-status-title">
            <div className={styles.statusHeader}>
              <h2 id="current-status-title">Status</h2>
              <p className={styles.currentStatus}>{detail.status}</p>
            </div>
            <dl className={styles.facts}>{detail.facts.map((fact) => <div key={fact.label}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>)}</dl>
          </section>
          <section className={styles.card} aria-labelledby="timeline-title">
            <div className={styles.statusHeader}><h2 id="timeline-title">Purchase timeline</h2></div>
            <ol className={styles.timeline}>{detail.timeline.map((event) => <li key={event.label} aria-label={`${event.label}: ${event.complete ? "complete" : "pending"}`}><span className={styles.marker} aria-hidden="true">{event.complete ? "✓" : null}</span><strong>{event.label}</strong><span className={styles.eventDate}>{event.date ? formatPurchaseDetailsDate(event.date) : "—"}</span></li>)}</ol>
          </section>
        </div>
        <section className={styles.card} aria-labelledby="refund-policy-title">
          <h2 id="refund-policy-title">Refund policy</h2>
          <p className={styles.policy}>{detail.policyNote}</p>
        </section>
      </div>
    </HomeHeaderCard>
  );
}
