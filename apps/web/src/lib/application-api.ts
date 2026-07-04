const defaultApiBaseUrl = "http://localhost:8000";

type ApiResponse<TData> = Readonly<{
  success: boolean;
  data: TData | null;
  error: { code: string; message: string } | null;
  meta: Record<string, unknown>;
}>;

type ApiUser = Readonly<{
  id: string;
  first_name: string;
  last_name: string;
  created_at: string;
  display_name: string;
  roles: readonly { key: string; name: string }[];
}>;

export type PurchaseType = "digital" | "physical" | "subscription";

type ApiPurchase = Readonly<{
  id: string;
  order_number: string;
  purchase_type: PurchaseType;
  product_name: string;
  sku: string;
  amount_cents: number;
  purchased_at: string;
  status: string;
  details_url: string;
}>;

type ApiDigitalPurchaseDetails = Readonly<{
  issued_code: string;
  code_redeemed: boolean;
  code_redeemed_at: string | null;
  code_invalidated_at: string | null;
  code_delivered_at: string | null;
  refund_window_expires_at: string;
  refund_lock_reason: string | null;
}>;

type ApiPhysicalPurchaseDetails = Readonly<{
  scheduled_delivery_at: string;
  delivered_at: string | null;
  return_status: string;
  carrier: string | null;
  tracking_number: string | null;
  return_barcode_generated: boolean;
  return_label_created_at: string | null;
  accepted_by_carrier_at: string | null;
  return_requested_at: string | null;
  return_authorized_at: string | null;
  return_received_at: string | null;
  return_rejected_at: string | null;
  return_rejection_reason: string | null;
  refund_window_expires_at: string;
}>;

type ApiSubscriptionPurchaseDetails = Readonly<{
  period_start: string;
  period_end: string;
  cancelled_at: string | null;
  service_ended_at: string | null;
  auto_renew: boolean;
  refund_proration_mode: string;
  full_refund_window_expires_at: string;
  refund_window_expires_at: string;
}>;

type ApiPurchaseDetails =
  | Readonly<{
      purchase_id: string;
      purchase_type: "digital";
      details: ApiDigitalPurchaseDetails;
    }>
  | Readonly<{
      purchase_id: string;
      purchase_type: "physical";
      details: ApiPhysicalPurchaseDetails;
    }>
  | Readonly<{
      purchase_id: string;
      purchase_type: "subscription";
      details: ApiSubscriptionPurchaseDetails;
    }>;

type ApiRefundWorkflow = Readonly<{
  purchase_id: string;
  purchase_type: PurchaseType;
  can_enter_refund_workflow: boolean;
  can_prepare_refund: boolean;
  can_issue_funds: boolean;
  refund_stage: "blocked" | "eligible" | "prepared" | "issued";
  required_action:
    | "none"
    | "request_refund"
    | "invalidate_code"
    | "generate_return_label"
    | "cancel_subscription"
    | "await_carrier_acceptance"
    | "issue_funds";
  refundable_amount_cents: number;
  refund_outcome: "none" | "full" | "prorated";
  reasons: readonly string[];
  policy_facts: Record<string, unknown>;
}>;

export type CustomerProfile = Readonly<{
  id: string;
  firstName: string;
  lastName: string;
  createdAt: string;
}>;

export type CustomerPurchase = Readonly<{
  id: string;
  orderNumber: string;
  purchaseType: PurchaseType;
  productName: string;
  amountCents: number;
  purchasedAt: string;
  status: string;
}>;

export type DigitalPurchaseDetails = Readonly<{
  issuedCode: string;
  codeRedeemed: boolean;
  codeRedeemedAt: string | null;
  codeInvalidatedAt: string | null;
  codeDeliveredAt: string | null;
  refundWindowExpiresAt: string;
  refundLockReason: string | null;
}>;

export type PhysicalPurchaseDetails = Readonly<{
  scheduledDeliveryAt: string;
  deliveredAt: string | null;
  returnStatus: string;
  carrier: string | null;
  trackingNumber: string | null;
  returnBarcodeGenerated: boolean;
  returnLabelCreatedAt: string | null;
  acceptedByCarrierAt: string | null;
  returnRequestedAt: string | null;
  returnAuthorizedAt: string | null;
  returnReceivedAt: string | null;
  returnRejectedAt: string | null;
  returnRejectionReason: string | null;
  refundWindowExpiresAt: string;
}>;

export type SubscriptionPurchaseDetails = Readonly<{
  periodStart: string;
  periodEnd: string;
  cancelledAt: string | null;
  serviceEndedAt: string | null;
  autoRenew: boolean;
  refundProrationMode: string;
  fullRefundWindowExpiresAt: string;
  refundWindowExpiresAt: string;
}>;

export type PurchaseDetails =
  | Readonly<{
      purchaseId: string;
      purchaseType: "digital";
      details: DigitalPurchaseDetails;
    }>
  | Readonly<{
      purchaseId: string;
      purchaseType: "physical";
      details: PhysicalPurchaseDetails;
    }>
  | Readonly<{
      purchaseId: string;
      purchaseType: "subscription";
      details: SubscriptionPurchaseDetails;
    }>;

export type RefundWorkflow = Readonly<{
  purchaseId: string;
  purchaseType: PurchaseType;
  canEnterRefundWorkflow: boolean;
  canPrepareRefund: boolean;
  canIssueFunds: boolean;
  refundStage: "blocked" | "eligible" | "prepared" | "issued";
  requiredAction:
    | "none"
    | "request_refund"
    | "invalidate_code"
    | "generate_return_label"
    | "cancel_subscription"
    | "await_carrier_acceptance"
    | "issue_funds";
  refundableAmountCents: number;
  refundOutcome: "none" | "full" | "prorated";
  reasons: readonly string[];
  policyFacts: Record<string, unknown>;
}>;

function getApiBaseUrl() {
  return process.env.REFUNDS_AI_API_BASE_URL ?? defaultApiBaseUrl;
}

export async function getUserProfile(userId: string) {
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/users/${userId}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    const body = (await response.json()) as ApiResponse<{ user: ApiUser }>;

    if (!body.success || !body.data) {
      return null;
    }

    return mapApiUserToCustomerProfile(body.data.user);
  } catch {
    return null;
  }
}

export async function getUserPurchases(userId: string) {
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/users/${userId}/purchases`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    const body = (await response.json()) as ApiResponse<{
      purchases: ApiPurchase[];
    }>;

    if (!body.success || !body.data) {
      return null;
    }

    return body.data.purchases.map(mapApiPurchaseToCustomerPurchase);
  } catch {
    return null;
  }
}

export async function getPurchaseDetails(purchaseId: string) {
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/api/purchases/${purchaseId}/details`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      return null;
    }

    const body = (await response.json()) as ApiResponse<ApiPurchaseDetails>;

    if (!body.success || !body.data) {
      return null;
    }

    return mapApiPurchaseDetailsToPurchaseDetails(body.data);
  } catch {
    return null;
  }
}

export async function getRefundWorkflow(purchaseId: string) {
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/api/purchases/${purchaseId}/refund/eligibility`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      return null;
    }

    const body = (await response.json()) as ApiResponse<ApiRefundWorkflow>;

    if (!body.success || !body.data) {
      return null;
    }

    return mapApiRefundWorkflowToRefundWorkflow(body.data);
  } catch {
    return null;
  }
}

export function mapApiUserToCustomerProfile(user: ApiUser): CustomerProfile {
  return {
    id: user.id,
    firstName: user.first_name,
    lastName: user.last_name,
    createdAt: user.created_at,
  };
}

export function mapApiPurchaseToCustomerPurchase(
  purchase: ApiPurchase,
): CustomerPurchase {
  return {
    id: purchase.id,
    orderNumber: purchase.order_number,
    purchaseType: purchase.purchase_type,
    productName: purchase.product_name,
    amountCents: purchase.amount_cents,
    purchasedAt: purchase.purchased_at,
    status: purchase.status,
  };
}

export function mapApiPurchaseDetailsToPurchaseDetails(
  purchaseDetails: ApiPurchaseDetails,
): PurchaseDetails {
  if (purchaseDetails.purchase_type === "digital") {
    return {
      purchaseId: purchaseDetails.purchase_id,
      purchaseType: purchaseDetails.purchase_type,
      details: {
        issuedCode: purchaseDetails.details.issued_code,
        codeRedeemed: purchaseDetails.details.code_redeemed,
        codeRedeemedAt: purchaseDetails.details.code_redeemed_at,
        codeInvalidatedAt: purchaseDetails.details.code_invalidated_at,
        codeDeliveredAt: purchaseDetails.details.code_delivered_at,
        refundWindowExpiresAt: purchaseDetails.details.refund_window_expires_at,
        refundLockReason: purchaseDetails.details.refund_lock_reason,
      },
    };
  }

  if (purchaseDetails.purchase_type === "subscription") {
    return {
      purchaseId: purchaseDetails.purchase_id,
      purchaseType: purchaseDetails.purchase_type,
      details: {
        periodStart: purchaseDetails.details.period_start,
        periodEnd: purchaseDetails.details.period_end,
        cancelledAt: purchaseDetails.details.cancelled_at,
        serviceEndedAt: purchaseDetails.details.service_ended_at,
        autoRenew: purchaseDetails.details.auto_renew,
        refundProrationMode: purchaseDetails.details.refund_proration_mode,
        fullRefundWindowExpiresAt:
          purchaseDetails.details.full_refund_window_expires_at,
        refundWindowExpiresAt: purchaseDetails.details.refund_window_expires_at,
      },
    };
  }

  return {
    purchaseId: purchaseDetails.purchase_id,
    purchaseType: purchaseDetails.purchase_type,
    details: {
      scheduledDeliveryAt: purchaseDetails.details.scheduled_delivery_at,
      deliveredAt: purchaseDetails.details.delivered_at,
      returnStatus: purchaseDetails.details.return_status,
      carrier: purchaseDetails.details.carrier,
      trackingNumber: purchaseDetails.details.tracking_number,
      returnBarcodeGenerated: purchaseDetails.details.return_barcode_generated,
      returnLabelCreatedAt: purchaseDetails.details.return_label_created_at,
      acceptedByCarrierAt: purchaseDetails.details.accepted_by_carrier_at,
      returnRequestedAt: purchaseDetails.details.return_requested_at,
      returnAuthorizedAt: purchaseDetails.details.return_authorized_at,
      returnReceivedAt: purchaseDetails.details.return_received_at,
      returnRejectedAt: purchaseDetails.details.return_rejected_at,
      returnRejectionReason: purchaseDetails.details.return_rejection_reason,
      refundWindowExpiresAt: purchaseDetails.details.refund_window_expires_at,
    },
  };
}

export function mapApiRefundWorkflowToRefundWorkflow(
  workflow: ApiRefundWorkflow,
): RefundWorkflow {
  return {
    purchaseId: workflow.purchase_id,
    purchaseType: workflow.purchase_type,
    canEnterRefundWorkflow: workflow.can_enter_refund_workflow,
    canPrepareRefund: workflow.can_prepare_refund,
    canIssueFunds: workflow.can_issue_funds,
    refundStage: workflow.refund_stage,
    requiredAction: workflow.required_action,
    refundableAmountCents: workflow.refundable_amount_cents,
    refundOutcome: workflow.refund_outcome,
    reasons: workflow.reasons,
    policyFacts: workflow.policy_facts,
  };
}

export function formatCentsAsDollars(amountCents: number) {
  return new Intl.NumberFormat("en-US", {
    currency: "USD",
    style: "currency",
  }).format(amountCents / 100);
}

export function formatPurchaseDate(purchasedAt: string) {
  const parsedDate = new Date(purchasedAt);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Purchased date unavailable";
  }

  return `Purchased ${new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
    year: "numeric",
  }).format(parsedDate)}`;
}

export function formatPurchaseStatus(status: string) {
  return status
    .split("_")
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}
