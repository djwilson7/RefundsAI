import { afterEach, describe, expect, it, vi } from "vitest";
import {
  formatCentsAsDollars,
  formatPurchaseDate,
  formatPurchaseStatus,
  getPurchaseDetails,
  getModelAuditInvocation,
  getModelAuditInvocationPage,
  getModelAuditInvocations,
  getModelAuditSessionDetail,
  getRefundWorkflow,
  getUserProfile,
  getUserPurchases,
  mapApiModelAuditSessionToInvocation,
  mapApiModelAuditSessionToDetail,
  mapApiPurchaseDetailsToPurchaseDetails,
  mapApiPurchaseToCustomerPurchase,
  mapApiRefundWorkflowToRefundWorkflow,
  mapApiUserToCustomerProfile,
} from "./application-api";

const apiUser = {
  id: "20000000-0000-4000-8000-000000000001",
  first_name: "Avery",
  last_name: "Brooks",
  created_at: "2026-07-03T00:00:00Z",
  display_name: "Avery Brooks",
  roles: [{ key: "customer", name: "Customer" }],
};

const apiPurchase = {
  id: "40000000-0000-4000-8000-000000000001",
  order_number: "RAI-10001",
  purchase_type: "physical" as const,
  product_name: "Wireless Headphones",
  sku: "PHY-HEADPHONES-001",
  amount_cents: 12999,
  purchased_at: "2026-06-20T14:30:00Z",
  status: "refund_pending",
  details_url: "/api/purchases/40000000-0000-4000-8000-000000000001/details",
};

const apiPhysicalPurchaseDetails = {
  purchase_id: "40000000-0000-4000-8000-000000000001",
  purchase_type: "physical" as const,
  details: {
    scheduled_delivery_at: "2026-06-22T14:30:00Z",
    delivered_at: null,
    return_status: "not_requested",
    carrier: "UPS",
    tracking_number: "TRK-RAI-10001",
    return_barcode_generated: false,
    return_label_created_at: null,
    accepted_by_carrier_at: null,
    return_requested_at: null,
    return_authorized_at: null,
    return_received_at: null,
    return_rejected_at: null,
    return_rejection_reason: null,
    refund_window_expires_at: "2026-07-20T14:30:00Z",
  },
};

const apiRefundWorkflow = {
  purchase_id: "40000000-0000-4000-8000-000000000003",
  purchase_type: "subscription" as const,
  can_enter_refund_workflow: true,
  can_prepare_refund: false,
  can_issue_funds: true,
  refund_stage: "prepared" as const,
  required_action: "issue_funds" as const,
  refundable_amount_cents: 1750,
  refund_outcome: "prorated" as const,
  reasons: [],
  policy_facts: {
    auto_renew: false,
  },
};

const apiModelAuditSession = {
  id: "70000000-0000-4000-8000-000000000001",
  trace_id: "71000000-0000-4000-8000-000000000001",
  conversation_id: null,
  customer_id: "20000000-0000-4000-8000-000000000001",
  request_id: "req-123",
  model_name: "gpt-5.4-mini",
  status: "succeeded",
  prompt_tokens: 500,
  completion_tokens: 312,
  total_tokens: 812,
  started_at: "2026-07-07T16:18:00Z",
  completed_at: "2026-07-07T16:18:03.200Z",
  latency_ms: 3200,
  original_prompt:
    "Can you check whether my wireless headphones are eligible for a refund?",
  event_count: 14,
  created_at: "2026-07-07T16:18:00Z",
  updated_at: "2026-07-07T16:18:03.200Z",
};

const apiModelAuditEvents = [
  {
    id: "73000000-0000-4000-8000-000000000001",
    session_id: apiModelAuditSession.id,
    trace_id: apiModelAuditSession.trace_id,
    sequence_number: 1,
    event_key: "REQUEST_RECEIVED",
    display_name: "Request received",
    category: "request",
    description: "Customer chat request accepted by the backend.",
    display_order: 1,
    workflow_kind: null,
    tool_name: null,
    summary: "FastAPI chat route received validated customer message.",
    input_json: {
      message:
        "Can you check whether my wireless headphones are eligible for a refund?",
    },
    output_json: null,
    metadata_json: { trace_event_type: "message.received" },
    created_at: "2026-07-07T16:18:00Z",
  },
  {
    id: "73000000-0000-4000-8000-000000000002",
    session_id: apiModelAuditSession.id,
    trace_id: apiModelAuditSession.trace_id,
    sequence_number: 6,
    event_key: "TOOL_COMPLETED",
    display_name: "Tool completed",
    category: "tool",
    description: "Backend tool execution completed.",
    display_order: 7,
    workflow_kind: "refund_eligibility",
    tool_name: "get_refund_eligibility",
    summary: "Backend refund-eligibility tool completed.",
    input_json: null,
    output_json: {
      tool: "get_refund_eligibility",
      summary: "refund eligible, next=request_refund",
      result: {
        refund_stage: "eligible",
        required_action: "request_refund",
      },
    },
    metadata_json: { trace_event_type: "tool_call.completed" },
    created_at: "2026-07-07T16:18:01Z",
  },
  {
    id: "73000000-0000-4000-8000-000000000003",
    session_id: apiModelAuditSession.id,
    trace_id: apiModelAuditSession.trace_id,
    sequence_number: 12,
    event_key: "RESPONSE_GENERATED",
    display_name: "Response generated",
    category: "response",
    description: "The assistant response was generated.",
    display_order: 12,
    workflow_kind: null,
    tool_name: null,
    summary: "The assistant response was generated.",
    input_json: null,
    output_json: {
      assistant_response: "Yes, the purchase is eligible for a refund.",
    },
    metadata_json: { trace_event_type: "response.generated" },
    created_at: "2026-07-07T16:18:03Z",
  },
];

const apiModelAuditEventsWithOnlyToolRequest = [
  {
    ...apiModelAuditEvents[0],
  },
  {
    ...apiModelAuditEvents[1],
    id: "73000000-0000-4000-8000-000000000004",
    sequence_number: 8,
    event_key: "TOOL_REQUESTED",
    display_name: "Tool requested",
    category: "tool",
    tool_name: "get_customer_purchase_history",
    summary: "Overriding model tool selection with deterministic workflow routing.",
    output_json: null,
    metadata_json: {
      trace_event_type: "tool_call.overridden",
      data: {
        requested_tool_name: "validate_customer_account",
        tool_name: "get_customer_purchase_history",
      },
    },
    created_at: "2026-07-07T16:18:01Z",
  },
];

describe("application API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps API user payloads to customer profiles", () => {
    expect(mapApiUserToCustomerProfile(apiUser)).toEqual({
      id: "20000000-0000-4000-8000-000000000001",
      firstName: "Avery",
      lastName: "Brooks",
      createdAt: "2026-07-03T00:00:00Z",
    });
  });

  it("maps API purchase payloads to customer purchases", () => {
    expect(mapApiPurchaseToCustomerPurchase(apiPurchase)).toEqual({
      id: "40000000-0000-4000-8000-000000000001",
      orderNumber: "RAI-10001",
      purchaseType: "physical",
      productName: "Wireless Headphones",
      amountCents: 12999,
      purchasedAt: "2026-06-20T14:30:00Z",
      status: "refund_pending",
    });
  });

  it("maps API purchase details payloads to type-specific purchase details", () => {
    expect(mapApiPurchaseDetailsToPurchaseDetails(apiPhysicalPurchaseDetails)).toEqual({
      purchaseId: "40000000-0000-4000-8000-000000000001",
      purchaseType: "physical",
      details: {
        scheduledDeliveryAt: "2026-06-22T14:30:00Z",
        deliveredAt: null,
        returnStatus: "not_requested",
        carrier: "UPS",
        trackingNumber: "TRK-RAI-10001",
        returnBarcodeGenerated: false,
        returnLabelCreatedAt: null,
        acceptedByCarrierAt: null,
        returnRequestedAt: null,
        returnAuthorizedAt: null,
        returnReceivedAt: null,
        returnRejectedAt: null,
        returnRejectionReason: null,
        refundWindowExpiresAt: "2026-07-20T14:30:00Z",
      },
    });
    expect(
      mapApiPurchaseDetailsToPurchaseDetails({
        purchase_id: "40000000-0000-4000-8000-000000000002",
        purchase_type: "digital",
        details: {
          issued_code: "DIG-RAI-10002",
          code_redeemed: true,
          code_redeemed_at: "2026-06-21T14:30:00Z",
          code_invalidated_at: null,
          code_delivered_at: "2026-06-20T14:30:00Z",
          refund_window_expires_at: "2026-07-05T14:30:00Z",
          refund_lock_reason: "code_redeemed",
        },
      }),
    ).toMatchObject({
      purchaseId: "40000000-0000-4000-8000-000000000002",
      purchaseType: "digital",
      details: {
        issuedCode: "DIG-RAI-10002",
        codeRedeemed: true,
        refundLockReason: "code_redeemed",
      },
    });
    expect(
      mapApiPurchaseDetailsToPurchaseDetails({
        purchase_id: "40000000-0000-4000-8000-000000000003",
        purchase_type: "subscription",
        details: {
          period_start: "2026-06-20T14:30:00Z",
          period_end: "2026-07-20T14:30:00Z",
          cancelled_at: null,
          service_ended_at: null,
          auto_renew: true,
          refund_proration_mode: "none",
          full_refund_window_expires_at: "2026-06-22T14:30:00Z",
          refund_window_expires_at: "2026-07-20T14:30:00Z",
        },
      }),
    ).toMatchObject({
      purchaseId: "40000000-0000-4000-8000-000000000003",
      purchaseType: "subscription",
      details: {
        autoRenew: true,
        refundProrationMode: "none",
      },
    });
  });

  it("maps API refund workflow payloads", () => {
    expect(mapApiRefundWorkflowToRefundWorkflow(apiRefundWorkflow)).toEqual({
      purchaseId: "40000000-0000-4000-8000-000000000003",
      purchaseType: "subscription",
      canEnterRefundWorkflow: true,
      canPrepareRefund: false,
      canIssueFunds: true,
      refundStage: "prepared",
      requiredAction: "issue_funds",
      refundableAmountCents: 1750,
      refundOutcome: "prorated",
      reasons: [],
      policyFacts: {
        auto_renew: false,
      },
    });
  });

  it("maps model audit session and events to invocation cards", () => {
    expect(
      mapApiModelAuditSessionToInvocation(
        apiModelAuditSession,
        apiModelAuditEvents,
      ),
    ).toEqual({
      id: "70000000-0000-4000-8000-000000000001",
      startedAt: "2026-07-07T16:18:00Z",
      title: "July 7, 2026",
      lastActive: "Last active 4:18 PM",
      description:
        "Can you check whether my wireless headphones are eligible for a refund?",
      status: "succeeded",
      eventCount: 14,
      toolCount: 1,
      failureCount: 0,
      totalTokens: 812,
      latency: "3.2s",
      timeToResponse: "3.0s",
    });
  });

  it("keeps deterministic audit cards at zero actual model tokens", () => {
    const invocation = mapApiModelAuditSessionToInvocation(
      {
        ...apiModelAuditSession,
        prompt_tokens: null,
        completion_tokens: null,
        total_tokens: 0,
        total_model_input_tokens_estimated: 0,
        total_model_output_tokens_estimated: 0,
        total_tool_input_tokens_estimated: 33,
        total_tool_output_tokens_estimated: 262,
      },
      apiModelAuditEvents,
    );

    expect(invocation.totalTokens).toBe(0);
  });

  it("maps model audit session and events to detail view data", () => {
    expect(
      mapApiModelAuditSessionToDetail(apiModelAuditSession, apiModelAuditEvents),
    ).toMatchObject({
      modelName: "gpt-5.4-mini",
      traceId: "71000000-0000-4000-8000-000000000001",
      requestId: "req-123",
      prompt:
        "Can you check whether my wireless headphones are eligible for a refund?",
      finalResponse: "Yes, the purchase is eligible for a refund.",
      toolCalls: [
        expect.objectContaining({
          toolName: "get_refund_eligibility",
          description:
            "Checks purchase facts and refund policy to determine whether the selected purchase is eligible and what must happen next.",
          status: "completed",
        }),
      ],
      timelineEvents: expect.arrayContaining([
        expect.objectContaining({
          title: "Customer request received",
          category: "request",
          summary:
            'Received customer request: "Can you check whether my wireless headphones are eligible for a refund?"',
        }),
        expect.objectContaining({
          title: "Backend operation completed",
          summary:
            "The backend completed get refund eligibility and recorded this result: refund eligible, next=request refund.",
          details: expect.arrayContaining([
            {
              label: "Refund stage",
              value: "eligible",
            },
          ]),
        }),
      ]),
    });
  });

  it("consolidates tool started and completed events by lifecycle id", () => {
    const completed = {
      ...apiModelAuditEvents[1],
      tool_call_id: "tool-call-1",
      status: "completed",
      latency_ms: 18,
      source: "deterministic_forced",
      operation: "list",
      backend_category: "backend_read",
      input_tokens_estimated: 3,
      output_tokens_estimated: 240,
      tokenizer: "tiktoken:cl100k_base",
      input_summary: "customer purchase history",
      output_summary: "4 purchases, $209.99",
    };
    const started = {
      ...completed,
      id: "73000000-0000-4000-8000-000000000099",
      sequence_number: 5,
      event_key: "TOOL_STARTED",
      display_name: "Tool started",
      status: "started",
      latency_ms: null,
      output_summary: null,
    };

    const detail = mapApiModelAuditSessionToDetail(
      apiModelAuditSession,
      [apiModelAuditEvents[0], started, completed, apiModelAuditEvents[2]],
    );

    expect(detail.toolCalls).toHaveLength(1);
    expect(detail.toolCalls[0]).toMatchObject({
      toolName: "get_refund_eligibility",
      description:
        "Checks purchase facts and refund policy to determine whether the selected purchase is eligible and what must happen next.",
      status: "completed",
      latency: "18ms",
      source: "deterministic_forced",
      operation: "list",
      inputSummary: "customer purchase history",
      outputSummary: "4 purchases, $209.99",
      inputTokensEstimated: 3,
      outputTokensEstimated: 240,
      tokenizer: "tiktoken:cl100k_base",
      backendCategory: "backend_read",
    });
    expect(
      detail.timelineEvents.find(
        (event) => event.title === "Backend operation completed",
      )?.tokenCount,
    ).toBe(243);
  });

  it("preserves every backend event in its original audit sequence", () => {
    const graphStarted = {
      ...apiModelAuditEvents[0],
      id: "73000000-0000-4000-8000-000000000010",
      sequence_number: 2,
      event_key: "GRAPH_STARTED",
      display_name: "Graph started",
      category: "routing",
      metadata_json: { trace_event_type: "graph.started" },
    };
    const toolStarted = {
      ...apiModelAuditEvents[1],
      id: "73000000-0000-4000-8000-000000000011",
      sequence_number: 5,
      event_key: "TOOL_STARTED",
      display_name: "Tool started",
      tool_call_id: "tool-call-1",
      metadata_json: { trace_event_type: "tool_call.executing" },
    };
    const toolCompleted = {
      ...apiModelAuditEvents[1],
      tool_call_id: "tool-call-1",
      metadata_json: { trace_event_type: "tool_call.completed" },
    };
    const responseReturned = {
      ...apiModelAuditEvents[2],
      id: "73000000-0000-4000-8000-000000000012",
      sequence_number: 13,
      event_key: "RESPONSE_RETURNED",
      display_name: "Response returned",
      metadata_json: { trace_event_type: "route.response_returned" },
    };

    const timeline = mapApiModelAuditSessionToDetail(apiModelAuditSession, [
      apiModelAuditEvents[0],
      graphStarted,
      toolStarted,
      toolCompleted,
      apiModelAuditEvents[2],
      responseReturned,
    ]).timelineEvents;

    expect(timeline.map((event) => event.title)).toEqual([
      "Customer request received",
      "Request processing started",
      "Backend operation started",
      "Backend operation completed",
      "Customer response prepared",
      "Response delivered",
    ]);
    expect(timeline.map((event) => event.sequenceNumber)).toEqual([
      1, 2, 5, 6, 12, 13,
    ]);
  });

  it("maps fallback audit fields, failure events, and workflow timeline variants", () => {
    const baseEvent = {
      ...apiModelAuditEvents[0],
      input_json: null,
      output_json: null,
      metadata_json: null,
      summary: null,
      description: null,
      created_at: "not-a-date",
      latency_ms: -1,
    };
    const detail = mapApiModelAuditSessionToDetail(
      {
        ...apiModelAuditSession,
        request_id: null,
        prompt_tokens: null,
        completion_tokens: null,
        total_tokens: null,
        started_at: "not-a-date",
        completed_at: null,
        updated_at: "not-a-date",
        latency_ms: null,
        original_prompt: null,
        total_workflow_steps: 7,
        total_model_calls: 3,
        total_tool_calls: 4,
        total_prompt_tokens: 11,
        total_completion_tokens: 12,
        total_reasoning_tokens: 2,
        total_model_latency_ms: 1400,
        total_tool_latency_ms: 25,
        total_model_input_tokens_estimated: 40,
        total_model_output_tokens_estimated: 5,
        total_tool_input_tokens_estimated: 7,
        total_tool_output_tokens_estimated: 9,
        total_workflow_latency_ms: 1500,
      },
      [
        {
          ...baseEvent,
          id: "event-tool-started",
          sequence_number: 2,
          event_key: "TOOL_STARTED",
          display_name: "Tool started",
          category: "tool",
          tool_name: "unknown_backend_tool",
          tool_call_id: "tool-call-started",
          status: "started",
        },
        {
          ...baseEvent,
          id: "event-mutation-completed",
          sequence_number: 3,
          event_key: "MUTATION_COMPLETED",
          display_name: "Mutation completed",
          category: "tool",
          metadata_json: {
            data: {
              requested_tool_name: "request_refund",
              active_workflow: { kind: "refund_mutation" },
              values: ["alpha", 2, true],
              nested_objects: [{ id: 1 }],
              empty_values: [],
            },
          },
        },
        {
          ...baseEvent,
          id: "event-error",
          sequence_number: 4,
          event_key: "ERROR_RAISED",
          display_name: "Error raised",
          category: "error",
          input_json: { tool_name: "issue_refund", reason: "backend rejected" },
        },
        {
          ...baseEvent,
          id: "event-classified",
          sequence_number: 5,
          event_key: "WORKFLOW_CLASSIFIED",
          display_name: "Workflow classified",
          category: "routing",
          input_json: { workflow: "refund_policy" },
          metadata_json: { trace_event_type: "workflow.classified" },
        },
        {
          ...baseEvent,
          id: "event-workflow-executing",
          sequence_number: 6,
          display_name: "Workflow executing",
          category: "workflow",
          metadata_json: { trace_event_type: "workflow.executing" },
        },
        {
          ...baseEvent,
          id: "event-workflow-completed",
          sequence_number: 7,
          display_name: "Workflow completed",
          category: "workflow",
          metadata_json: { trace_event_type: "workflow.completed" },
        },
        {
          ...baseEvent,
          id: "event-eligibility-reconciled",
          sequence_number: 8,
          display_name: "Eligibility reconciled",
          category: "workflow",
          metadata_json: { trace_event_type: "workflow.eligibility_reconciled" },
        },
        {
          ...baseEvent,
          id: "event-confirmation-requested",
          sequence_number: 9,
          display_name: "Confirmation requested",
          category: "workflow",
          metadata_json: { trace_event_type: "workflow.confirmation_requested" },
        },
        {
          ...baseEvent,
          id: "event-confirmation-generated",
          sequence_number: 10,
          display_name: "Confirmation generated",
          category: "workflow",
          metadata_json: {
            trace_event_type: "workflow.confirmation_command_generated",
          },
        },
        {
          ...baseEvent,
          id: "event-confirmation-validated",
          sequence_number: 11,
          display_name: "Confirmation validated",
          category: "workflow",
          metadata_json: { trace_event_type: "workflow.confirmation_validated" },
        },
        {
          ...baseEvent,
          id: "event-mutation-lifecycle",
          sequence_number: 12,
          display_name: "Mutation lifecycle",
          category: "workflow",
          output_json: {
            final_stage: "issued",
            required_action: "none",
          },
          metadata_json: {
            trace_event_type: "workflow.refund_mutation_lifecycle",
          },
        },
        {
          ...baseEvent,
          id: "event-response-returned",
          sequence_number: 13,
          event_key: "RESPONSE_RETURNED",
          display_name: "Response returned",
          category: "response",
          output_json: {
            response:
              "This response is intentionally long enough to exercise the timeline truncation branch. ".repeat(
                4,
              ),
          },
        },
        {
          ...baseEvent,
          id: "event-response-generated-summary",
          sequence_number: 14,
          event_key: "RESPONSE_GENERATED",
          display_name: "Response generated",
          category: "response",
          summary: "Response generated without payload text.",
          output_json: {},
        },
        {
          ...baseEvent,
          id: "event-default",
          sequence_number: 15,
          display_name: "Default display",
          category: "workflow",
        },
      ],
    );

    expect(detail.invocation).toMatchObject({
      title: "Date unavailable",
      lastActive: "Last active unavailable",
      description: "Original prompt unavailable",
      failureCount: 1,
      latency: "unknown",
      timeToResponse: "unknown",
      totalTokens: 0,
    });
    expect(detail.requestId).toBe("Unavailable");
    expect(detail.metrics).toMatchObject({
      workflowSteps: 7,
      modelCalls: 3,
      toolCalls: 4,
      promptTokens: 11,
      completionTokens: 12,
      reasoningTokens: 2,
      estimatedInputTokens: 47,
      estimatedOutputTokens: 14,
      modelLatency: "1.4s",
      toolLatency: "25ms",
      workflowLatency: "1.5s",
    });
    expect(detail.finalResponse).toMatch(/^This response is intentionally long/);
    expect(detail.toolCalls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          toolName: "unknown_backend_tool",
          description: expect.stringContaining("Runs a backend operation"),
          status: "started",
          summary: "Tool event recorded.",
          inputSummary: "Not recorded",
          outputSummary: "Not recorded",
          latency: "unknown",
        }),
        expect.objectContaining({
          toolName: "request_refund",
          status: "completed",
        }),
        expect.objectContaining({
          toolName: "issue_refund",
          status: "failed",
        }),
      ]),
    );
    expect(detail.timelineEvents).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          title: "Process failed",
          summary: "issue refund selected.",
        }),
        expect.objectContaining({
          title: "Request understood",
          summary: "The request was understood as refund policy.",
        }),
        expect.objectContaining({
          title: "Workflow execution started",
        }),
        expect.objectContaining({
          title: "Backend workflow completed",
        }),
        expect.objectContaining({
          title: "Eligibility result verified",
        }),
        expect.objectContaining({
          title: "Customer confirmation required",
          summary:
            "The refund is eligible, but execution requires explicit customer confirmation.",
        }),
        expect.objectContaining({
          title: "Confirmation instructions prepared",
          summary:
            "The backend prepared the confirmation instruction for the customer.",
        }),
        expect.objectContaining({
          title: "Customer confirmation verified",
        }),
        expect.objectContaining({
          title: "Refund workflow updated",
          summary:
            "The refund workflow advanced to issued with no further action required.",
        }),
        expect.objectContaining({
          title: "Response generated",
          summary: "Response generated without payload text.",
        }),
        expect.objectContaining({
          title: "Default display",
          summary: "Audit event recorded.",
        }),
      ]),
    );
    expect(
      detail.timelineEvents.find((event) => event.id === "event-mutation-completed")
        ?.details,
    ).toEqual(
      expect.arrayContaining([
        { label: "Workflow", value: "refund_mutation" },
        { label: "Values", value: "alpha, 2, true" },
        { label: "Nested Objects", value: "1 items" },
      ]),
    );
  });

  it("distinguishes workflow events that share the classified database key", () => {
    const stateUpdated = {
      ...apiModelAuditEvents[0],
      id: "73000000-0000-4000-8000-000000000020",
      sequence_number: 10,
      event_key: "WORKFLOW_CLASSIFIED",
      display_name: "Workflow classified",
      category: "routing",
      workflow_kind: "refund_eligibility",
      input_json: {
        kind: "refund_eligibility",
        active_purchase: { product_name: "Smart Watch" },
      },
      metadata_json: { trace_event_type: "workflow.state_updated" },
    };
    const confirmationRequested = {
      ...stateUpdated,
      id: "73000000-0000-4000-8000-000000000021",
      sequence_number: 11,
      input_json: {
        kind: "refund_eligibility",
        expected_command: "Confirm start return and issue label",
      },
      metadata_json: { trace_event_type: "workflow.confirmation_requested" },
    };

    const timeline = mapApiModelAuditSessionToDetail(apiModelAuditSession, [
      stateUpdated,
      confirmationRequested,
    ]).timelineEvents;

    expect(timeline).toMatchObject([
      {
        sequenceNumber: 10,
        title: "Conversation context updated",
        summary:
          "The conversation context was updated with the selected purchase, workflow result, and next expected action.",
      },
      {
        sequenceNumber: 11,
        title: "Customer confirmation required",
        summary:
          'The refund is eligible, but execution requires the customer to submit this exact confirmation: "Confirm start return and issue label".',
      },
    ]);
  });

  it("prefers the exact response returned to the user", () => {
    const responseReturnedEvent = {
      ...apiModelAuditEvents[2],
      id: "73000000-0000-4000-8000-000000000004",
      sequence_number: 13,
      event_key: "RESPONSE_RETURNED",
      display_name: "Route response returned",
      summary: "FastAPI chat route returning assistant response payload.",
      output_json: {
        response: {
          message: {
            role: "assistant",
            content: "This is the exact response delivered to the user.",
          },
        },
      },
    };

    expect(
      mapApiModelAuditSessionToDetail(apiModelAuditSession, [
        ...apiModelAuditEvents,
        responseReturnedEvent,
      ]).finalResponse,
    ).toBe("This is the exact response delivered to the user.");
  });

  it("preserves repeated completed tool calls in session history", () => {
    const repeatedToolEvent = {
      ...apiModelAuditEvents[1],
      id: "73000000-0000-4000-8000-000000000099",
      sequence_number: 10,
      summary: "A second refund-eligibility tool call completed.",
      created_at: "2026-07-07T16:18:02Z",
    };

    expect(
      mapApiModelAuditSessionToDetail(apiModelAuditSession, [
        ...apiModelAuditEvents,
        repeatedToolEvent,
      ]).toolCalls,
    ).toEqual([
      expect.objectContaining({
        id: "73000000-0000-4000-8000-000000000002",
        toolName: "get_refund_eligibility",
      }),
      expect.objectContaining({
        id: "73000000-0000-4000-8000-000000000099",
        toolName: "get_refund_eligibility",
      }),
    ]);
  });

  it("counts deterministic tool usage from persisted tool request events", () => {
    expect(
      mapApiModelAuditSessionToInvocation(
        apiModelAuditSession,
        apiModelAuditEventsWithOnlyToolRequest,
      ),
    ).toMatchObject({
      toolCount: 1,
    });
  });

  it("does not display TTR above total session latency", () => {
    expect(
      mapApiModelAuditSessionToInvocation(
        {
          ...apiModelAuditSession,
          latency_ms: 11_200,
        },
        [
          apiModelAuditEvents[0],
          {
            ...apiModelAuditEvents[2],
            created_at: "2026-07-07T16:18:18.100Z",
          },
        ],
      ),
    ).toMatchObject({
      latency: "11.2s",
      timeToResponse: "11.2s",
    });
  });

  it("loads a user profile from the backend API", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          data: { user: apiUser },
          error: null,
          meta: {},
        }),
    });
    vi.stubGlobal("fetch", fetch);

    await expect(getUserProfile(apiUser.id)).resolves.toEqual({
      id: "20000000-0000-4000-8000-000000000001",
      firstName: "Avery",
      lastName: "Brooks",
      createdAt: "2026-07-03T00:00:00Z",
    });
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/users/20000000-0000-4000-8000-000000000001",
      { cache: "no-store" },
    );
  });

  it("loads purchase history from the backend API", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          data: { purchases: [apiPurchase] },
          error: null,
          meta: {},
        }),
    });
    vi.stubGlobal("fetch", fetch);

    await expect(getUserPurchases(apiUser.id)).resolves.toEqual([
      {
        id: "40000000-0000-4000-8000-000000000001",
        orderNumber: "RAI-10001",
        purchaseType: "physical",
        productName: "Wireless Headphones",
        amountCents: 12999,
        purchasedAt: "2026-06-20T14:30:00Z",
        status: "refund_pending",
      },
    ]);
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/users/20000000-0000-4000-8000-000000000001/purchases",
      { cache: "no-store" },
    );
  });

  it("loads purchase details from the backend API", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          data: apiPhysicalPurchaseDetails,
          error: null,
          meta: {},
        }),
    });
    vi.stubGlobal("fetch", fetch);

    await expect(getPurchaseDetails(apiPurchase.id)).resolves.toEqual({
      purchaseId: "40000000-0000-4000-8000-000000000001",
      purchaseType: "physical",
      details: {
        scheduledDeliveryAt: "2026-06-22T14:30:00Z",
        deliveredAt: null,
        returnStatus: "not_requested",
        carrier: "UPS",
        trackingNumber: "TRK-RAI-10001",
        returnBarcodeGenerated: false,
        returnLabelCreatedAt: null,
        acceptedByCarrierAt: null,
        returnRequestedAt: null,
        returnAuthorizedAt: null,
        returnReceivedAt: null,
        returnRejectedAt: null,
        returnRejectionReason: null,
        refundWindowExpiresAt: "2026-07-20T14:30:00Z",
      },
    });
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/purchases/40000000-0000-4000-8000-000000000001/details",
      { cache: "no-store" },
    );
  });

  it("loads refund workflow from the backend API", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          data: apiRefundWorkflow,
          error: null,
          meta: {},
        }),
    });
    vi.stubGlobal("fetch", fetch);

    await expect(
      getRefundWorkflow("40000000-0000-4000-8000-000000000003"),
    ).resolves.toMatchObject({
      purchaseId: "40000000-0000-4000-8000-000000000003",
      purchaseType: "subscription",
      refundableAmountCents: 1750,
      refundOutcome: "prorated",
      refundStage: "prepared",
    });
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/purchases/40000000-0000-4000-8000-000000000003/refund/eligibility",
      { cache: "no-store" },
    );
  });

  it("loads model audit invocation summaries from the session API", async () => {
    const fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          data: { sessions: [apiModelAuditSession] },
          error: null,
          meta: {},
        }),
    });
    vi.stubGlobal("fetch", fetch);

    await expect(getModelAuditInvocations(1)).resolves.toEqual([
      expect.objectContaining({
        description:
          "Can you check whether my wireless headphones are eligible for a refund?",
        eventCount: 14,
        latency: "3.2s",
        timeToResponse: "3.2s",
        toolCount: 0,
      }),
    ]);
    expect(fetch).toHaveBeenNthCalledWith(
      1,
      "/api/admin/audit/sessions?limit=2",
      { cache: "no-store" },
    );
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("loads all model audit invocations when no limit is supplied", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: { sessions: [apiModelAuditSession] },
            error: null,
            meta: {},
          }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: { events: apiModelAuditEvents },
            error: null,
            meta: {},
          }),
      });
    vi.stubGlobal("fetch", fetch);

    await expect(getModelAuditInvocations()).resolves.toHaveLength(1);
    expect(fetch).toHaveBeenNthCalledWith(
      1,
      "/api/admin/audit/sessions",
      { cache: "no-store" },
    );
  });

  it("loads paged model audit invocations with offset and has-more state", async () => {
    const secondApiModelAuditSession = {
      ...apiModelAuditSession,
      id: "70000000-0000-4000-8000-000000000002",
      started_at: "2026-07-07T15:18:00Z",
    };
    const fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: {
              sessions: [apiModelAuditSession, secondApiModelAuditSession],
            },
            error: null,
            meta: {},
          }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: { events: apiModelAuditEvents },
            error: null,
            meta: {},
          }),
      });
    vi.stubGlobal("fetch", fetch);

    await expect(
      getModelAuditInvocationPage({ limit: 1, offset: 10 }),
    ).resolves.toMatchObject({
      hasMore: true,
      invocations: [
        expect.objectContaining({
          id: "70000000-0000-4000-8000-000000000001",
        }),
      ],
    });
    expect(fetch).toHaveBeenNthCalledWith(
      1,
      "/api/admin/audit/sessions?limit=2&offset=10",
      { cache: "no-store" },
    );
  });

  it("loads one model audit session detail from session and event APIs", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: { session: apiModelAuditSession },
            error: null,
            meta: {},
          }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: { events: apiModelAuditEvents },
            error: null,
            meta: {},
          }),
      });
    vi.stubGlobal("fetch", fetch);

    await expect(getModelAuditSessionDetail(apiModelAuditSession.id)).resolves.toMatchObject({
      modelName: "gpt-5.4-mini",
      prompt:
        "Can you check whether my wireless headphones are eligible for a refund?",
      toolCalls: [
        expect.objectContaining({
          toolName: "get_refund_eligibility",
        }),
      ],
    });
    expect(fetch).toHaveBeenNthCalledWith(
      1,
      "/api/admin/audit/sessions/70000000-0000-4000-8000-000000000001",
      { cache: "no-store" },
    );
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      "/api/admin/audit/sessions/70000000-0000-4000-8000-000000000001/events",
      { cache: "no-store" },
    );
  });

  it("returns null when a single audit invocation cannot load its session or events", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({ ok: false })
        .mockResolvedValueOnce({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              data: { events: apiModelAuditEvents },
            }),
        }),
    );

    await expect(getModelAuditInvocation(apiModelAuditSession.id)).resolves.toBeNull();

    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              data: { session: apiModelAuditSession },
            }),
        })
        .mockResolvedValueOnce({ ok: false }),
    );

    await expect(getModelAuditInvocation(apiModelAuditSession.id)).resolves.toBeNull();
  });

  it("returns null when audit session detail cannot load events", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              data: { session: apiModelAuditSession },
            }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ success: false, data: null }),
        }),
    );

    await expect(getModelAuditSessionDetail(apiModelAuditSession.id)).resolves.toBeNull();
  });

  it("maps paged audit sessions with no event payload as empty event history", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              data: { sessions: [{ ...apiModelAuditSession, original_prompt: null }] },
              error: null,
              meta: {},
            }),
        })
        .mockResolvedValueOnce({ ok: false }),
    );

    await expect(getModelAuditInvocationPage({ limit: 1 })).resolves.toMatchObject({
      hasMore: false,
      invocations: [
        expect.objectContaining({
          description: "Original prompt unavailable",
          toolCount: 0,
        }),
      ],
    });
  });

  it("returns null when the user API is unavailable or unsuccessful", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(getUserProfile(apiUser.id)).resolves.toBeNull();

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    await expect(getUserProfile(apiUser.id)).resolves.toBeNull();

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, data: null }),
    }));
    await expect(getUserProfile(apiUser.id)).resolves.toBeNull();
  });

  it("returns null when the purchases API is unavailable or unsuccessful", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(getUserPurchases(apiUser.id)).resolves.toBeNull();

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    await expect(getUserPurchases(apiUser.id)).resolves.toBeNull();

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, data: null }),
    }));
    await expect(getUserPurchases(apiUser.id)).resolves.toBeNull();
  });

  it("returns null when the purchase details API is unavailable or unsuccessful", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(getPurchaseDetails(apiPurchase.id)).resolves.toBeNull();

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    await expect(getPurchaseDetails(apiPurchase.id)).resolves.toBeNull();

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: false, data: null }),
      }),
    );
    await expect(getPurchaseDetails(apiPurchase.id)).resolves.toBeNull();
  });

  it("returns null when the refund workflow API is unavailable or unsuccessful", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(getRefundWorkflow(apiPurchase.id)).resolves.toBeNull();

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    await expect(getRefundWorkflow(apiPurchase.id)).resolves.toBeNull();

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: false, data: null }),
      }),
    );
    await expect(getRefundWorkflow(apiPurchase.id)).resolves.toBeNull();
  });

  it("returns null when the model audit sessions API is unavailable or unsuccessful", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(getModelAuditInvocations()).resolves.toBeNull();

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    await expect(getModelAuditInvocations()).resolves.toBeNull();

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: false, data: null }),
      }),
    );
    await expect(getModelAuditInvocations()).resolves.toBeNull();
  });

  it("formats purchase values for display", () => {
    expect(formatCentsAsDollars(12999)).toBe("$129.99");
    expect(formatPurchaseDate("2026-06-20T14:30:00Z")).toBe(
      "Purchased Jun 20, 2026",
    );
    expect(formatPurchaseDate("not-a-date")).toBe("Purchased date unavailable");
    expect(formatPurchaseStatus("refund_pending")).toBe("Refund Pending");
  });
});
