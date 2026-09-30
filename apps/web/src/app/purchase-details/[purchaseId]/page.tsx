import { PurchaseDetailsPlaceholder } from "@/components/purchase-details-placeholder";
import { getPurchaseDetails, getRefundWorkflow } from "@/lib/application-api";
import { notFound } from "next/navigation";
import { findMockCustomerById, mockCustomers } from "@/components/mock-customers";
import { isDemoModeEnabled } from "@/lib/demo-mode";
import { buildDemoPurchaseDetail } from "@/lib/demo-purchase-detail";
import { TourPurchaseDetails } from "@/components/tour-purchase-details";
export const dynamic = "force-dynamic";

type PurchaseDetailsPageProps = Readonly<{
  params: Promise<{
    purchaseId: string;
  }>;
  searchParams: Promise<{ customerId?: string; tour?: string }>;
}>;

export default async function PurchaseDetailsPage({
  params,
  searchParams,
}: PurchaseDetailsPageProps) {
  const { purchaseId } = await params;
  const { customerId, tour } = await searchParams;
  if (isDemoModeEnabled() || tour === "client") {
    const customer = findMockCustomerById(customerId ?? mockCustomers[0].id);
    if (!customer) notFound();
    const detail = buildDemoPurchaseDetail(customer.id, purchaseId, new Date().toISOString());
    if (!detail) notFound();
    return <TourPurchaseDetails customer={customer} detail={detail} />;
  }
  const [purchaseDetails, refundWorkflow] = await Promise.all([
    getPurchaseDetails(purchaseId),
    getRefundWorkflow(purchaseId),
  ]);

  return (
    <PurchaseDetailsPlaceholder
      currentDate={new Date().toISOString()}
      purchaseDetails={purchaseDetails}
      purchaseId={purchaseId}
      refundWorkflow={refundWorkflow}
    />
  );
}
