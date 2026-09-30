import { AdminHomePage } from "@/components/admin-home-page";
import { getModelAuditInvocationPage } from "@/lib/application-api";
import { buildDemoAuditSessions } from "@/lib/demo-audit";
import { isDemoModeEnabled } from "@/lib/demo-mode";

const auditSessionPageSize = 10;
export const dynamic = "force-dynamic";

export default async function AdminHome({ searchParams }: Readonly<{ searchParams: Promise<{ tour?: string }> }>) {
  if (isDemoModeEnabled() || (await searchParams).tour === "admin") {
    const sessions = buildDemoAuditSessions(new Date().toISOString());
    return <AdminHomePage tour hasMoreInvocations={false} invocations={sessions.map((session) => session.invocation)} />;
  }
  const auditPage = await getModelAuditInvocationPage({
    limit: auditSessionPageSize,
  });

  return (
    <AdminHomePage
      hasMoreInvocations={auditPage?.hasMore ?? false}
      invocations={auditPage?.invocations ?? []}
    />
  );
}
