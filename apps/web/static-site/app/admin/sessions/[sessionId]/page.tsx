import { buildDemoAuditSessions } from "@/lib/demo-audit";
import { DemoScreen } from "../../../demo-screen";

export function generateStaticParams() {
  return buildDemoAuditSessions(new Date().toISOString()).map((session) => ({ sessionId: session.invocation.id }));
}

export default async function AuditPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = await params;
  return <DemoScreen perspective="audit" id={sessionId} />;
}
