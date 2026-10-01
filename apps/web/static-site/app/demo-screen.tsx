"use client";

import { useSyncExternalStore } from "react";
import { CustomerMainScreen } from "@/components/customer-main-screen";
import { AdminHomePage } from "@/components/admin-home-page";
import { AdminSessionDetailPage } from "@/components/admin-session-detail-page";
import { TourPurchaseDetails } from "@/components/tour-purchase-details";
import { mockCustomers } from "@/components/mock-customers";
import { buildDemoPurchases } from "@/lib/demo-purchases";
import { buildDemoPurchaseDetail } from "@/lib/demo-purchase-detail";
import { buildDemoAuditSessions } from "@/lib/demo-audit";

// Hydrate the exported snapshot first, then use today's UTC day in the browser.
// Snapshot strings remain stable throughout the day; no network or stored objects.
const subscribe = () => () => {};
const today = () => `${new Date().toISOString().slice(0, 10)}T14:00:00Z`;
const exportedDate = () => process.env.NEXT_PUBLIC_REFUNDS_AI_STATIC_REFERENCE_DATE!;

type DemoScreenProps =
  | { perspective: "client" }
  | { perspective: "admin" }
  | { perspective: "purchase"; id: string }
  | { perspective: "audit"; id: string };

export function DemoScreen(props: DemoScreenProps) {
  const referenceDate = useSyncExternalStore(subscribe, today, exportedDate);
  const customer = mockCustomers[0];
  if (props.perspective === "client") {
    return <CustomerMainScreen customer={customer} purchases={buildDemoPurchases(customer.id, referenceDate)} demo />;
  }
  if (props.perspective === "purchase") {
    const detail = buildDemoPurchaseDetail(customer.id, props.id, referenceDate);
    return detail ? <TourPurchaseDetails customer={customer} detail={detail} /> : null;
  }
  const sessions = buildDemoAuditSessions(referenceDate);
  if (props.perspective === "admin") {
    return <AdminHomePage tour hasMoreInvocations={false} invocations={sessions.map((item) => item.invocation)} />;
  }
  const detail = sessions.find((item) => item.invocation.id === props.id);
  return detail ? <AdminSessionDetailPage tour detail={detail} sessionId={props.id} /> : null;
}
