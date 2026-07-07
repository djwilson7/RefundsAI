import Link from "next/link";
import { AdminAuditLiveUpdates } from "./admin-audit-live-updates";
import { AppCard } from "./app-card";
import type { ModelAuditSessionDetail } from "@/lib/application-api";
import styles from "./admin-session-detail-page.module.css";

type AdminSessionDetailPageProps = Readonly<{
  detail: ModelAuditSessionDetail | null;
  sessionId: string;
}>;

export function AdminSessionDetailPage({
  detail,
  sessionId,
}: AdminSessionDetailPageProps) {
  if (!detail) {
    return (
      <main className={styles.page}>
        <AppCard className={styles.content}>
          <Link className={styles.backLink} href="/admin-home">
            Back to audit history
          </Link>
          <p className={styles.eyebrow}>Session Detail</p>
          <h1 className={styles.heading}>Audit session unavailable</h1>
          <p className={styles.summary}>
            Session {sessionId} could not be loaded from the audit API.
          </p>
        </AppCard>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <AdminAuditLiveUpdates sessionId={detail.invocation.id} />
      <AppCard className={styles.content}>
        <Link className={styles.backLink} href="/admin-home">
          Back to audit history
        </Link>
        <p className={styles.eyebrow}>Session Detail</p>
        <div className={styles.header}>
          <div>
            <h1 className={styles.heading}>{detail.invocation.title}</h1>
            <p className={styles.summary}>{detail.prompt}</p>
          </div>
          <span className={getStatusClassName(detail.invocation.status)}>
            {detail.invocation.status}
          </span>
        </div>

        <dl className={styles.metaGrid}>
          <div>
            <dt>Model</dt>
            <dd>{detail.modelName}</dd>
          </div>
          <div>
            <dt>Trace</dt>
            <dd>{detail.traceId}</dd>
          </div>
          <div>
            <dt>Request</dt>
            <dd>{detail.requestId}</dd>
          </div>
          <div>
            <dt>Events</dt>
            <dd>{detail.invocation.eventCount}</dd>
          </div>
          <div>
            <dt>Tools</dt>
            <dd>{detail.invocation.toolCount}</dd>
          </div>
          <div>
            <dt>Tokens</dt>
            <dd>{detail.invocation.totalTokens}</dd>
          </div>
          <div>
            <dt>Latency</dt>
            <dd>{detail.invocation.latency}</dd>
          </div>
          <div>
            <dt>TTR</dt>
            <dd>{detail.invocation.timeToResponse}</dd>
          </div>
        </dl>
      </AppCard>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Model Response</h2>
        <article className={styles.panel}>
          <p className={styles.responseText}>{detail.finalResponse}</p>
        </article>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Tool History</h2>
        {detail.toolCalls.length > 0 ? (
          <div className={styles.toolGrid}>
            {detail.toolCalls.map((toolCall) => (
              <article className={styles.panel} key={toolCall.id}>
                <div className={styles.panelHeader}>
                  <h3>{toolCall.toolName}</h3>
                  <span>{toolCall.status}</span>
                </div>
                <p>{toolCall.summary}</p>
                <p className={styles.timestamp}>{toolCall.occurredAt}</p>
              </article>
            ))}
          </div>
        ) : (
          <p className={styles.emptyState}>No tool calls were recorded.</p>
        )}
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Execution Timeline</h2>
        <ol className={styles.timeline}>
          {detail.timelineEvents.map((event) => (
            <li className={styles.timelineItem} key={event.id}>
              <span className={styles.sequence}>{event.sequenceNumber}</span>
              <div>
                <div className={styles.timelineHeader}>
                  <h3>{event.title}</h3>
                  <span>{event.category}</span>
                </div>
                <p>{event.summary}</p>
                <p className={styles.timestamp}>{event.occurredAt}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}

function getStatusClassName(status: string) {
  if (status === "succeeded") {
    return `${styles.statusPill} ${styles.statusSucceeded}`;
  }

  if (status === "failed") {
    return `${styles.statusPill} ${styles.statusFailed}`;
  }

  if (status === "running") {
    return `${styles.statusPill} ${styles.statusRunning}`;
  }

  return styles.statusPill;
}
