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
  reasoning_tokens?: number | null;
  total_tokens: number | null;
  started_at: string;
  completed_at: string | null;
  latency_ms: number | null;
  event_count: number;
  total_model_calls?: number;
  total_tool_calls?: number;
  total_prompt_tokens?: number;
  total_completion_tokens?: number;
  total_reasoning_tokens?: number;
  total_model_latency_ms?: number;
  total_tool_latency_ms?: number;
  total_model_input_tokens_estimated?: number;
  total_model_output_tokens_estimated?: number;
  total_tool_input_tokens_estimated?: number;
  total_tool_output_tokens_estimated?: number;
  total_workflow_latency_ms?: number | null;
  total_workflow_steps?: number;
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
  model_call_id?: string | null;
  phase?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  reasoning_tokens?: number | null;
  total_tokens?: number | null;
  latency_ms?: number | null;
  status?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  tool_call_id?: string | null;
  source?: string | null;
  operation?: string | null;
  backend_category?: string | null;
  input_tokens_estimated?: number | null;
  output_tokens_estimated?: number | null;
  tokenizer?: string | null;
  token_budget?: Record<string, unknown> | null;
  input_summary?: string | null;
  output_summary?: string | null;
  customer_id?: string | null;
  purchase_id?: string | null;
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
  startedAt: string;
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
  latency: string;
  source: string;
  operation: string;
  workflow: string;
  inputSummary: string;
  outputSummary: string;
  inputTokensEstimated: number | null;
  outputTokensEstimated: number | null;
  tokenizer: string | null;
  backendCategory: string;
  customerId: string | null;
  purchaseId: string | null;
}>;

export type ModelAuditTimelineEvent = Readonly<{
  id: string;
  sequenceNumber: number;
  title: string;
  category: string;
  summary: string;
  details: readonly Readonly<{
    label: string;
    value: string;
  }>[];
  occurredAt: string;
  status: string | null;
  latency: string | null;
  tokenCount: number | null;
  workflow: string | null;
  operation: string | null;
  rawPayload: string | null;
}>;

export type ModelAuditSessionMetrics = Readonly<{
  duration: string;
  workflowSteps: number;
  modelCalls: number;
  toolCalls: number;
  promptTokens: number;
  completionTokens: number;
  reasoningTokens: number;
  totalTokens: number;
  estimatedInputTokens: number;
  estimatedOutputTokens: number;
  modelLatency: string;
  toolLatency: string;
  workflowLatency: string;
}>;

export type ModelAuditSessionDetail = Readonly<{
  invocation: ModelAuditInvocation;
  modelName: string;
  traceId: string;
  requestId: string;
  metrics: ModelAuditSessionMetrics;
  prompt: string;
  finalResponse: string;
  toolCalls: readonly ModelAuditToolCall[];
  timelineEvents: readonly ModelAuditTimelineEvent[];
}>;

function getApiBaseUrl() {
  return process.env.REFUNDS_AI_API_BASE_URL ?? defaultApiBaseUrl;
}

function getAuditReadBaseUrl() {
  return typeof window === "undefined" ? getApiBaseUrl() : "";
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

export async function getModelAuditInvocations(limit?: number) {
  const page = await getModelAuditInvocationPage({ limit });

  return page?.invocations ?? null;
}

export async function getModelAuditInvocationPage({
  limit,
  offset = 0,
}: {
  limit?: number;
  offset?: number;
} = {}) {
  try {
    const requestedLimit = limit === undefined ? undefined : limit + 1;
    const query = new URLSearchParams();

    if (requestedLimit !== undefined) {
      query.set("limit", String(requestedLimit));
    }

    if (offset > 0) {
      query.set("offset", String(offset));
    }

    const queryString = query.toString() ? `?${query.toString()}` : "";
    const response = await fetch(
      `${getAuditReadBaseUrl()}/api/admin/audit/sessions${queryString}`,
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

    const sessions =
      limit === undefined ? body.data.sessions : body.data.sessions.slice(0, limit);
    const invocations = await Promise.all(
      sessions.map(async (session) => {
        const events = await getModelAuditSessionEvents(session.id);

        return mapApiModelAuditSessionToInvocation(session, events ?? []);
      }),
    );

    return {
      invocations,
      hasMore: limit === undefined ? false : body.data.sessions.length > limit,
    };
  } catch {
    return null;
  }
}

export async function getModelAuditInvocation(sessionId: string) {
  try {
    const [session, events] = await Promise.all([
      getModelAuditSession(sessionId),
      getModelAuditSessionEvents(sessionId),
    ]);

    if (!session || !events) {
      return null;
    }

    return mapApiModelAuditSessionToInvocation(session, events);
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
      `${getAuditReadBaseUrl()}/api/admin/audit/sessions/${sessionId}`,
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
      `${getAuditReadBaseUrl()}/api/admin/audit/sessions/${sessionId}/events`,
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
    startedAt: session.started_at,
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
    metrics: {
      duration: formatDuration(session.latency_ms),
      workflowSteps: session.total_workflow_steps ?? session.event_count,
      modelCalls: session.total_model_calls ?? 0,
      toolCalls: session.total_tool_calls ?? countToolInvocations(events),
      promptTokens: session.total_prompt_tokens ?? session.prompt_tokens ?? 0,
      completionTokens:
        session.total_completion_tokens ?? session.completion_tokens ?? 0,
      reasoningTokens: session.total_reasoning_tokens ?? 0,
      totalTokens: session.total_tokens ?? 0,
      estimatedInputTokens:
        (session.total_model_input_tokens_estimated ?? 0) +
        (session.total_tool_input_tokens_estimated ?? 0),
      estimatedOutputTokens:
        (session.total_model_output_tokens_estimated ?? 0) +
        (session.total_tool_output_tokens_estimated ?? 0),
      modelLatency: formatDuration(session.total_model_latency_ms ?? null),
      toolLatency: formatDuration(session.total_tool_latency_ms ?? null),
      workflowLatency: formatDuration(
        session.total_workflow_latency_ms ?? session.latency_ms,
      ),
    },
    prompt: getOriginalPrompt(events),
    finalResponse: getFinalResponse(events),
    toolCalls: getToolCalls(events),
    timelineEvents: events.map(mapApiModelAuditEventToTimelineEvent),
  };
}

function getFinalResponse(events: readonly ApiModelAuditEvent[]) {
  const responseEvents = [
    events.find((event) => event.event_key === "RESPONSE_RETURNED"),
    events.find((event) => event.event_key === "RESPONSE_GENERATED"),
  ];

  for (const event of responseEvents) {
    const response = getResponseText(event?.output_json);

    if (response) {
      return response;
    }
  }

  return (
    responseEvents.find((event) => event?.summary)?.summary ??
    "Final response unavailable"
  );
}

function getResponseText(payload: Record<string, unknown> | null | undefined) {
  if (!payload) {
    return null;
  }

  if (
    typeof payload.assistant_response === "string" &&
    payload.assistant_response.trim()
  ) {
    return payload.assistant_response;
  }

  const response = payload.response;
  if (typeof response === "string" && response.trim()) {
    return response;
  }

  if (isRecord(response)) {
    const message = response.message;

    if (
      isRecord(message) &&
      typeof message.content === "string" &&
      message.content.trim()
    ) {
      return message.content;
    }
  }

  return null;
}

function getToolCalls(events: readonly ApiModelAuditEvent[]) {
  const toolEvents = events.filter(
    (event) => event.tool_call_id || isTerminalToolEvent(event),
  );
  const callsById = new Map<string, ModelAuditToolCall>();

  for (const event of toolEvents) {
    const toolName = getEventToolName(event);

    if (!toolName) {
      continue;
    }

    const lifecycleId = event.tool_call_id ?? `legacy:${event.id}`;
    callsById.set(
      lifecycleId,
      mapApiModelAuditEventToToolCall(event, toolName),
    );
  }

  return [...callsById.values()].sort(
    (first, second) => first.sequenceNumber - second.sequenceNumber,
  );
}

function isTerminalToolEvent(event: ApiModelAuditEvent) {
  return (
    event.event_key === "TOOL_COMPLETED" ||
    event.event_key === "MUTATION_COMPLETED" ||
    event.event_key === "ERROR_RAISED" ||
    event.category === "error"
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
    latency: formatDuration(event.latency_ms ?? null),
    source: event.source ?? "Unavailable",
    operation: event.operation ?? "Unavailable",
    workflow: event.workflow_kind ?? "Unavailable",
    inputSummary:
      event.input_summary ?? summarizeAuditPayload(event.input_json),
    outputSummary:
      event.output_summary ?? summarizeAuditPayload(event.output_json),
    inputTokensEstimated: event.input_tokens_estimated ?? null,
    outputTokensEstimated: event.output_tokens_estimated ?? null,
    tokenizer: event.tokenizer ?? null,
    backendCategory: event.backend_category ?? "Unavailable",
    customerId: event.customer_id ?? null,
    purchaseId: event.purchase_id ?? null,
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

function mapApiModelAuditEventToTimelineEvent(
  event: ApiModelAuditEvent,
): ModelAuditTimelineEvent {
  return {
    id: event.id,
    sequenceNumber: event.sequence_number,
    title: event.display_name,
    category: event.category,
    summary: getTimelineEventSummary(event),
    details: getTimelineEventDetails(event),
    occurredAt: formatAuditTime(event.created_at),
    status: event.status ?? null,
    latency:
      event.latency_ms === null || event.latency_ms === undefined
        ? null
        : formatDuration(event.latency_ms),
    tokenCount:
      event.total_tokens ??
      sumNullable(event.input_tokens_estimated, event.output_tokens_estimated),
    workflow: event.workflow_kind,
    operation: event.operation ?? null,
    rawPayload:
      event.input_json || event.output_json || event.metadata_json
        ? JSON.stringify(
            {
              input: event.input_json,
              output: event.output_json,
              metadata: event.metadata_json,
            },
            null,
            2,
          )
        : null,
  };
}

function summarizeAuditPayload(payload: Record<string, unknown> | null) {
  if (!payload) {
    return "Not recorded";
  }
  const summary = findStringValue(payload, "summary");
  return summary ?? `${Object.keys(payload).length} recorded fields`;
}

function getTimelineEventSummary(event: ApiModelAuditEvent) {
  const toolName = getEventToolName(event);
  const message = event.input_json?.message;

  if (
    event.event_key === "REQUEST_RECEIVED" &&
    typeof message === "string" &&
    message.trim()
  ) {
    return `Received customer request: "${message}"`;
  }

  if (toolName) {
    const resultSummary = findStringValue(event.output_json, "summary");

    if (event.event_key === "TOOL_COMPLETED" && resultSummary) {
      return `${formatEventValue(toolName)} completed: ${resultSummary}.`;
    }

    const action =
      event.event_key === "TOOL_COMPLETED"
        ? "completed"
        : event.event_key === "TOOL_STARTED"
          ? "started"
          : "selected";
    return `${formatEventValue(toolName)} ${action}.`;
  }

  const workflow =
    findStringValue(event.input_json, "kind") ??
    findStringValue(event.input_json, "workflow");
  const reason = findStringValue(event.input_json, "reason");

  if (event.event_key === "WORKFLOW_CLASSIFIED" && workflow) {
    return reason
      ? `Classified the request as ${formatEventValue(workflow)} because ${reason}.`
      : `Classified the request as ${formatEventValue(workflow)}.`;
  }

  if (
    event.event_key === "RESPONSE_GENERATED" ||
    event.event_key === "RESPONSE_RETURNED"
  ) {
    const response = getResponseText(event.output_json);
    return response
      ? `${event.event_key === "RESPONSE_RETURNED" ? "Returned" : "Generated"} a ${response.length}-character response for the customer.`
      : (event.summary ?? event.description ?? "Assistant response recorded.");
  }

  return event.summary ?? event.description ?? "Audit event recorded.";
}

function getTimelineEventDetails(event: ApiModelAuditEvent) {
  const details: Array<{ label: string; value: string }> = [];
  const seen = new Set<string>();
  const ignoredKeys = new Set([
    "assistant_response",
    "content",
    "message",
    "response_preview",
    "trace_event_type",
  ]);

  for (const [source, payload] of [
    ["Input", event.input_json],
    ["Result", event.output_json],
    ["Metadata", isRecord(event.metadata_json?.data) ? event.metadata_json.data : null],
  ] as const) {
    collectTimelineFacts(payload, source, details, seen, ignoredKeys);
  }

  return details.slice(0, 8);
}

function collectTimelineFacts(
  value: unknown,
  path: string,
  details: Array<{ label: string; value: string }>,
  seen: Set<string>,
  ignoredKeys: ReadonlySet<string>,
) {
  if (details.length >= 8 || value === null || value === undefined) {
    return;
  }

  if (isRecord(value)) {
    for (const [key, nestedValue] of Object.entries(value)) {
      if (!ignoredKeys.has(key)) {
        collectTimelineFacts(
          nestedValue,
          `${path} / ${formatEventLabel(key)}`,
          details,
          seen,
          ignoredKeys,
        );
      }
    }
    return;
  }

  const formattedValue = formatTimelineFactValue(value);
  if (!formattedValue) {
    return;
  }

  const fingerprint = `${path}:${formattedValue}`;
  if (!seen.has(fingerprint)) {
    seen.add(fingerprint);
    details.push({ label: path, value: formattedValue });
  }
}

function formatTimelineFactValue(value: unknown) {
  if (typeof value === "string") {
    return value.trim() || null;
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (Array.isArray(value)) {
    const scalarValues = value.filter(
      (item) =>
        typeof item === "string" ||
        typeof item === "number" ||
        typeof item === "boolean",
    );
    return scalarValues.length === value.length && value.length > 0
      ? scalarValues.map(String).join(", ")
      : value.length > 0
        ? `${value.length} items`
        : null;
  }

  return null;
}

function findStringValue(
  value: Record<string, unknown> | null,
  key: string,
): string | null {
  if (!value) {
    return null;
  }

  const directValue = value[key];
  if (typeof directValue === "string" && directValue.trim()) {
    return directValue;
  }

  for (const nestedValue of Object.values(value)) {
    if (isRecord(nestedValue)) {
      const match = findStringValue(nestedValue, key);
      if (match) {
        return match;
      }
    }
  }

  return null;
}

function formatEventLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatEventValue(value: string) {
  return value.replaceAll("_", " ");
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

function sumNullable(
  first: number | null | undefined,
  second: number | null | undefined,
) {
  if (first === null && second === null) {
    return null;
  }

  if (first === undefined && second === undefined) {
    return null;
  }

  return (first ?? 0) + (second ?? 0);
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
