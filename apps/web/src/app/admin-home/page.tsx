import { AdminHomePage } from "@/components/admin-home-page";
import { getModelAuditInvocations } from "@/lib/application-api";

export default async function AdminHome() {
  const invocations = (await getModelAuditInvocations()) ?? [];

  return <AdminHomePage invocations={invocations} />;
}
