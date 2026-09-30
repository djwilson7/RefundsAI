import { HomeHeaderCard } from "./home-header-card";
import type { ModelAuditInvocation } from "@/lib/application-api";
import { AdminAuditSessionList } from "./admin-audit-session-list";
import styles from "./admin-home-page.module.css";
import { AdminAuditSummary } from "./admin-audit-summary";

type AdminHomePageProps = Readonly<{
  hasMoreInvocations: boolean;
  invocations: readonly ModelAuditInvocation[];
  tour?: boolean;
}>;

export function AdminHomePage({
  hasMoreInvocations,
  invocations,
  tour = false,
}: AdminHomePageProps) {
  return (
    <HomeHeaderCard
      eyebrow="Agentic Refund Model History"
      heading="System Administrator"
      summary="Model performance and audit session review"
      productBanner={tour}
      tourRole="admin"
    >
      {tour ? <AdminAuditSummary invocations={invocations} /> : null}
      <section
        aria-labelledby="session-memory-title"
        className={styles.sessionOverview}
      >
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle} id="session-memory-title">
            {tour ? "Simulated Audit History" : "Audit History"}
          </h2>
        </div>

        <AdminAuditSessionList
          initialHasMore={hasMoreInvocations}
          initialInvocations={invocations}
          tour={tour}
        />
      </section>
    </HomeHeaderCard>
  );
}
