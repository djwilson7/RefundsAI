import Link from "next/link";
import { HomeHeaderCard } from "./home-header-card";
import { ArrowRightIcon } from "./icons";
import type { ModelAuditInvocation } from "@/lib/application-api";
import { AdminAuditLiveUpdates } from "./admin-audit-live-updates";
import styles from "./admin-home-page.module.css";

type AdminHomePageProps = Readonly<{
  invocations: readonly ModelAuditInvocation[];
}>;

export function AdminHomePage({ invocations }: AdminHomePageProps) {
  return (
    <HomeHeaderCard
      eyebrow="Agentic Refund Model History"
      heading="System Administrator"
      summary="Model performance and audit session review"
    >
      <AdminAuditLiveUpdates />
      <section
        aria-labelledby="session-memory-title"
        className={styles.sessionOverview}
      >
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle} id="session-memory-title">
            Audit History
          </h2>
        </div>

        {invocations.length > 0 ? (
          <div className={styles.sessionGrid}>
            {invocations.map((invocation) => (
              <Link
                className={styles.sessionCard}
                href={`/admin/sessions/${invocation.id}`}
                key={invocation.id}
              >
                <div className={styles.cardHeader}>
                  <h3 className={styles.cardTitle}>{invocation.title}</h3>
                  <span className={styles.actionSlot}>
                    <time className={styles.lastActive}>
                      {invocation.lastActive}
                    </time>
                    <span className={styles.viewSession}>
                      <span>View Session</span>
                      <ArrowRightIcon />
                    </span>
                  </span>
                </div>

                <p className={styles.description}>{invocation.description}</p>

                <div className={styles.metaRows} aria-label="Invocation metadata">
                  <p className={styles.metaRow}>
                    <span className={getStatusClassName(invocation.status)}>
                      {invocation.status}
                    </span>
                    <span>{formatCount(invocation.eventCount, "event")}</span>
                    <span>{formatCount(invocation.toolCount, "tool")}</span>
                    <span>{formatCount(invocation.failureCount, "failure")}</span>
                  </p>
                  <p className={styles.metaRow}>
                    <span>{invocation.totalTokens} tokens</span>
                    <span>{invocation.latency} latency</span>
                    <span>{invocation.timeToResponse} TTR</span>
                  </p>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <p className={styles.emptyState}>No model invocations captured yet.</p>
        )}
      </section>
    </HomeHeaderCard>
  );
}

function getStatusClassName(status: string) {
  if (status === "succeeded") {
    return styles.statusSucceeded;
  }

  if (status === "failed") {
    return styles.statusFailed;
  }

  if (status === "running") {
    return styles.statusRunning;
  }

  return undefined;
}

function formatCount(count: number, label: string) {
  return `${count} ${label}${count === 1 ? "" : "s"}`;
}
