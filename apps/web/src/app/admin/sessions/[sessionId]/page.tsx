import { AdminSessionDetailPage } from "@/components/admin-session-detail-page";
import { getModelAuditSessionDetail } from "@/lib/application-api";

type AdminSessionPageProps = Readonly<{
  params: Promise<{
    sessionId: string;
  }>;
}>;

export default async function AdminSessionPage({ params }: AdminSessionPageProps) {
  const { sessionId } = await params;
  const detail = await getModelAuditSessionDetail(sessionId);

  return <AdminSessionDetailPage detail={detail} sessionId={sessionId} />;
}
