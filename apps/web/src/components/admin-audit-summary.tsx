import type { ModelAuditInvocation } from "@/lib/application-api";
import { summarizeAuditInvocations } from "@/lib/audit-summary";
import styles from "./admin-home-page.module.css";

export function AdminAuditSummary({ invocations }: Readonly<{ invocations: readonly ModelAuditInvocation[] }>) {
  const summary = summarizeAuditInvocations(invocations);
  return (
    <section className={styles.summarySection} aria-label="Audit performance summary">
      <dl className={styles.summaryGrid}>
        <div className={styles.summaryCard}><dt>Audit Sessions</dt><dd>{summary.sessions}</dd></div>
        <div className={styles.summaryCard}>
          <dt>Session Outcomes</dt>
          <dd className={styles.outcomeValues}>
            <span><strong>{summary.succeeded}</strong><span>Success</span></span>
            <span><strong>{summary.failed}</strong><span>Failure</span></span>
          </dd>
        </div>
        <div className={styles.summaryCard}><dt>Total Token Usage</dt><dd>{summary.totalTokens.toLocaleString("en-US")}</dd></div>
      </dl>
      <dl className={styles.averageGrid}>
        <div><dt>Avg. Events</dt><dd>{summary.averageEvents}</dd></div>
        <div><dt>Avg. Tool Calls</dt><dd>{summary.averageTools}</dd></div>
        <div><dt>Avg. Latency</dt><dd>{summary.averageLatency}</dd></div>
        <div><dt>Avg. Time to Response</dt><dd>{summary.averageTtr}</dd></div>
      </dl>
    </section>
  );
}
