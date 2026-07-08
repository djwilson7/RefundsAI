import { AdminHomePage } from "@/components/admin-home-page";
import { getModelAuditInvocationPage } from "@/lib/application-api";

const auditSessionPageSize = 10;

export default async function AdminHome() {
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
