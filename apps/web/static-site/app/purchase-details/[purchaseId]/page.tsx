import { mockCustomers } from "@/components/mock-customers";
import { buildDemoPurchases } from "@/lib/demo-purchases";
import { DemoScreen } from "../../demo-screen";

export function generateStaticParams() {
  return buildDemoPurchases(mockCustomers[0].id).map((purchase) => ({ purchaseId: purchase.id }));
}

export default async function PurchasePage({ params }: { params: Promise<{ purchaseId: string }> }) {
  const { purchaseId } = await params;
  return <DemoScreen perspective="purchase" id={purchaseId} />;
}
