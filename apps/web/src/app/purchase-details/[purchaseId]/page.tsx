import { PurchaseDetailsPlaceholder } from "@/components/purchase-details-placeholder";
import { getPurchaseDetails, getRefundWorkflow } from "@/lib/application-api";

type PurchaseDetailsPageProps = Readonly<{
  params: Promise<{
    purchaseId: string;
  }>;
}>;

export default async function PurchaseDetailsPage({
  params,
}: PurchaseDetailsPageProps) {
  const { purchaseId } = await params;
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
