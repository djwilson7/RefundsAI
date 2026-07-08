import { HomeHeaderCard } from "./home-header-card";
import type { ModelAuditInvocation } from "@/lib/application-api";
import { AdminAuditSessionList } from "./admin-audit-session-list";
import styles from "./admin-home-page.module.css";

type AdminHomePageProps = Readonly<{
  hasMoreInvocations: boolean;
  invocations: readonly ModelAuditInvocation[];
}>;

export function AdminHomePage({
  hasMoreInvocations,
  invocations,
}: AdminHomePageProps) {
  return (
    <HomeHeaderCard
      eyebrow="Agentic Refund Model History"
      heading="System Administrator"
      summary="Model performance and audit session review"
    >
      <section
        aria-labelledby="session-memory-title"
        className={styles.sessionOverview}
      >
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle} id="session-memory-title">
            Audit History
          </h2>
        </div>

        <AdminAuditSessionList
          initialHasMore={hasMoreInvocations}
          initialInvocations={invocations}
        />
      </section>
    </HomeHeaderCard>
  );
}
