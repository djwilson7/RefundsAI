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

type ApiModelAuditSession = Readonly<{
  id: string;
  trace_id: string;
  conversation_id: string | null;
  customer_id: string | null;
  request_id: string | null;
  model_name: string;
  status: string;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  started_at: string;
  completed_at: string | null;
  latency_ms: number | null;
  event_count: number;
  created_at: string;
  updated_at: string;
}>;

type ApiModelAuditEvent = Readonly<{
  id: string;
  session_id: string;
  trace_id: string;
  sequence_number: number;
  event_key: string;
  display_name: string;
  category: string;
  description: string | null;
  display_order: number;
  workflow_kind: string | null;
  tool_name: string | null;
  summary: string | null;
  input_json: Record<string, unknown> | null;
  output_json: Record<string, unknown> | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
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

export type ModelAuditInvocation = Readonly<{
  id: string;
  title: string;
  lastActive: string;
  description: string;
  status: string;
  eventCount: number;
  toolCount: number;
  failureCount: number;
  totalTokens: number;
  latency: string;
  timeToResponse: string;
}>;

export type ModelAuditToolCall = Readonly<{
  id: string;
  sequenceNumber: number;
  title: string;
  toolName: string;
  summary: string;
  occurredAt: string;
  status: "completed" | "started" | "requested" | "failed";
}>;

export type ModelAuditTimelineEvent = Readonly<{
  id: string;
  sequenceNumber: number;
  title: string;
  category: string;
  summary: string;
  occurredAt: string;
}>;

export type ModelAuditSessionDetail = Readonly<{
  invocation: ModelAuditInvocation;
  modelName: string;
  traceId: string;
  requestId: string;
  prompt: string;
  finalResponse: string;
  toolCalls: readonly ModelAuditToolCall[];
  timelineEvents: readonly ModelAuditTimelineEvent[];
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

export async function getModelAuditInvocations(limit = 4) {
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/api/admin/audit/sessions?limit=${limit}`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      return null;
    }

    const body = (await response.json()) as ApiResponse<{
      sessions: ApiModelAuditSession[];
    }>;

    if (!body.success || !body.data) {
      return null;
    }

    const invocations = await Promise.all(
      body.data.sessions.map(async (session) => {
        const events = await getModelAuditSessionEvents(session.id);

        return mapApiModelAuditSessionToInvocation(session, events ?? []);
      }),
    );

    return invocations;
  } catch {
    return null;
  }
}

export async function getModelAuditSessionDetail(sessionId: string) {
  try {
    const [session, events] = await Promise.all([
      getModelAuditSession(sessionId),
      getModelAuditSessionEvents(sessionId),
    ]);

    if (!session || !events) {
      return null;
    }

    return mapApiModelAuditSessionToDetail(session, events);
  } catch {
    return null;
  }
}

async function getModelAuditSession(sessionId: string) {
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/api/admin/audit/sessions/${sessionId}`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      return null;
    }

    const body = (await response.json()) as ApiResponse<{
      session: ApiModelAuditSession;
    }>;

    if (!body.success || !body.data) {
      return null;
    }

    return body.data.session;
  } catch {
    return null;
  }
}

async function getModelAuditSessionEvents(sessionId: string) {
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/api/admin/audit/sessions/${sessionId}/events`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      return null;
    }

    const body = (await response.json()) as ApiResponse<{
      events: ApiModelAuditEvent[];
    }>;

    if (!body.success || !body.data) {
      return null;
    }

    return body.data.events;
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

export function mapApiModelAuditSessionToInvocation(
  session: ApiModelAuditSession,
  events: readonly ApiModelAuditEvent[],
): ModelAuditInvocation {
  return {
    id: session.id,
    title: formatAuditDate(session.started_at),
    lastActive: formatAuditLastActive(session.completed_at ?? session.updated_at),
    description: getOriginalPrompt(events),
    status: session.status,
    eventCount: session.event_count,
    toolCount: countToolInvocations(events),
    failureCount: countFailures(events),
    totalTokens: session.total_tokens ?? 0,
    latency: formatDuration(session.latency_ms),
    timeToResponse: formatTimeToResponse(session.started_at, events, session.latency_ms),
  };
}

export function mapApiModelAuditSessionToDetail(
  session: ApiModelAuditSession,
  events: readonly ApiModelAuditEvent[],
): ModelAuditSessionDetail {
  return {
    invocation: mapApiModelAuditSessionToInvocation(session, events),
    modelName: session.model_name,
    traceId: session.trace_id,
    requestId: session.request_id ?? "Unavailable",
    prompt: getOriginalPrompt(events),
    finalResponse: getFinalResponse(events),
    toolCalls: getToolCalls(events),
    timelineEvents: events.map(mapApiModelAuditEventToTimelineEvent),
  };
}

function getFinalResponse(events: readonly ApiModelAuditEvent[]) {
  const responseEvent =
    events.find((event) => event.event_key === "RESPONSE_GENERATED") ??
    events.find((event) => event.event_key === "RESPONSE_RETURNED");
  const response = responseEvent?.output_json?.response;

  if (typeof response === "string" && response.trim()) {
    return response;
  }

  if (isRecord(response)) {
    const message = response.message;

    if (isRecord(message) && typeof message.content === "string") {
      return message.content;
    }
  }

  return responseEvent?.summary ?? "Final response unavailable";
}

function getToolCalls(events: readonly ApiModelAuditEvent[]) {
  const toolEvents = events.filter((event) => getEventToolName(event));
  const callsByTool = new Map<string, ModelAuditToolCall>();

  for (const event of toolEvents) {
    const toolName = getEventToolName(event);

    if (!toolName) {
      continue;
    }

    const currentCall = callsByTool.get(toolName);
    const nextCall = mapApiModelAuditEventToToolCall(event, toolName);

    if (
      currentCall === undefined ||
      toolStatusRank(nextCall.status) >= toolStatusRank(currentCall.status)
    ) {
      callsByTool.set(toolName, nextCall);
    }
  }

  return [...callsByTool.values()].sort(
    (first, second) => first.sequenceNumber - second.sequenceNumber,
  );
}

function mapApiModelAuditEventToToolCall(
  event: ApiModelAuditEvent,
  toolName: string,
): ModelAuditToolCall {
  return {
    id: event.id,
    sequenceNumber: event.sequence_number,
    title: event.display_name,
    toolName,
    summary: event.summary ?? event.description ?? "Tool event recorded.",
    occurredAt: formatAuditTime(event.created_at),
    status: getToolStatus(event),
  };
}

function getToolStatus(event: ApiModelAuditEvent): ModelAuditToolCall["status"] {
  if (event.event_key === "TOOL_COMPLETED" || event.event_key === "MUTATION_COMPLETED") {
    return "completed";
  }

  if (event.event_key === "TOOL_STARTED" || event.event_key === "MUTATION_STARTED") {
    return "started";
  }

  if (event.event_key === "ERROR_RAISED" || event.category === "error") {
    return "failed";
  }

  return "requested";
}

function toolStatusRank(status: ModelAuditToolCall["status"]) {
  return {
    failed: 4,
    completed: 3,
    started: 2,
    requested: 1,
  }[status];
}

function mapApiModelAuditEventToTimelineEvent(
  event: ApiModelAuditEvent,
): ModelAuditTimelineEvent {
  return {
    id: event.id,
    sequenceNumber: event.sequence_number,
    title: event.display_name,
    category: event.category,
    summary: event.summary ?? event.description ?? "Audit event recorded.",
    occurredAt: formatAuditTime(event.created_at),
  };
}

function getOriginalPrompt(events: readonly ApiModelAuditEvent[]) {
  const requestEvent = events.find((event) => event.event_key === "REQUEST_RECEIVED");
  const message = requestEvent?.input_json?.message;

  return typeof message === "string" && message.trim()
    ? message
    : "Original prompt unavailable";
}

function countToolInvocations(events: readonly ApiModelAuditEvent[]) {
  const completedToolNames = getDistinctToolNames(
    events.filter((event) => event.event_key === "TOOL_COMPLETED"),
  );

  if (completedToolNames.size > 0) {
    return completedToolNames.size;
  }

  const toolEventNames = getDistinctToolNames(
    events.filter((event) =>
      [
        "TOOL_COMPLETED",
        "TOOL_STARTED",
        "TOOL_REQUESTED",
        "MUTATION_COMPLETED",
        "MUTATION_STARTED",
      ].includes(event.event_key),
    ),
  );

  if (toolEventNames.size > 0) {
    return toolEventNames.size;
  }

  return getDistinctToolNames(events).size;
}

function getDistinctToolNames(events: readonly ApiModelAuditEvent[]) {
  const toolNames = new Set<string>();

  for (const event of events) {
    const toolName = getEventToolName(event);

    if (toolName) {
      toolNames.add(toolName);
    }
  }

  return toolNames;
}

function getEventToolName(event: ApiModelAuditEvent) {
  if (event.tool_name) {
    return event.tool_name;
  }

  const metadataData = event.metadata_json?.data;
  if (isRecord(metadataData)) {
    for (const key of ["tool_name", "requested_tool_name"]) {
      const value = metadataData[key];

      if (typeof value === "string" && value) {
        return value;
      }
    }
  }

  for (const payload of [event.input_json, event.output_json]) {
    if (!payload) {
      continue;
    }

    const value = payload.tool_name;

    if (typeof value === "string" && value) {
      return value;
    }
  }

  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function countFailures(events: readonly ApiModelAuditEvent[]) {
  return events.filter(
    (event) => event.event_key === "ERROR_RAISED" || event.category === "error",
  ).length;
}

function formatTimeToResponse(
  startedAt: string,
  events: readonly ApiModelAuditEvent[],
  fallbackLatencyMs: number | null,
) {
  const responseGeneratedEvent = events.find(
    (event) => event.event_key === "RESPONSE_GENERATED",
  );

  if (!responseGeneratedEvent) {
    return formatDuration(fallbackLatencyMs);
  }

  const started = new Date(startedAt);
  const responseGenerated = new Date(responseGeneratedEvent.created_at);

  if (
    Number.isNaN(started.getTime()) ||
    Number.isNaN(responseGenerated.getTime())
  ) {
    return formatDuration(fallbackLatencyMs);
  }

  const responseDurationMs = responseGenerated.getTime() - started.getTime();
  const displayedDurationMs =
    fallbackLatencyMs !== null
      ? Math.min(responseDurationMs, fallbackLatencyMs)
      : responseDurationMs;

  return formatDuration(displayedDurationMs);
}

function formatAuditDate(value: string) {
  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Date unavailable";
  }

  return new Intl.DateTimeFormat("en-US", {
    day: "numeric",
    month: "long",
    timeZone: "UTC",
    year: "numeric",
  }).format(parsedDate);
}

function formatAuditLastActive(value: string) {
  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Last active unavailable";
  }

  return `Last active ${new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(parsedDate)}`;
}

function formatAuditTime(value: string) {
  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return "Time unavailable";
  }

  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "UTC",
  }).format(parsedDate);
}

function formatDuration(durationMs: number | null) {
  if (durationMs === null || !Number.isFinite(durationMs) || durationMs < 0) {
    return "unknown";
  }

  if (durationMs < 1000) {
    return `${durationMs}ms`;
  }

  return `${(durationMs / 1000).toFixed(1)}s`;
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
