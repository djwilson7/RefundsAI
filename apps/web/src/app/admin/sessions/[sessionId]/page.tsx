import { AdminSessionDetailPage } from "@/components/admin-session-detail-page";
import { getModelAuditSessionDetail } from "@/lib/application-api";
import { buildDemoAuditSessions } from "@/lib/demo-audit";
import { notFound } from "next/navigation";
import { isDemoModeEnabled } from "@/lib/demo-mode";
export const dynamic = "force-dynamic";

type AdminSessionPageProps = Readonly<{
  searchParams: Promise<{ tour?: string }>;
  params: Promise<{
    sessionId: string;
  }>;
}>;

export default async function AdminSessionPage({ params, searchParams }: AdminSessionPageProps) {
  const { sessionId } = await params;
  if (isDemoModeEnabled() || (await searchParams).tour === "admin") {
    const detail = buildDemoAuditSessions(new Date().toISOString()).find((session) => session.invocation.id === sessionId);
    if (!detail) notFound();
    return <AdminSessionDetailPage tour detail={detail} sessionId={sessionId} />;
  }
  const detail = await getModelAuditSessionDetail(sessionId);

  return <AdminSessionDetailPage detail={detail} sessionId={sessionId} />;
}
