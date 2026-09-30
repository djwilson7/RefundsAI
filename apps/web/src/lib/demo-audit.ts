import type { ModelAuditSessionDetail } from "./application-api";
import { mockCustomers } from "@/components/mock-customers";

// Illustrative completed traces, never persisted or used to authorize live actions.
const scenarios = [
  { title: "Purchase history lookup", prompt: "Show me my recent purchases.", response: "Your recent purchases include digital products, physical orders, and subscriptions. Each purchase includes its order number, date, and amount.", tool: "get_customer_purchase_history", purpose: "Read the selected customer's purchase history.", outcome: "Returned 12 purchases belonging to Avery Brooks.", workflow: "purchase_history", operation: "list", model: true },
  { title: "Digital refund policy", prompt: "What is the refund policy for digital purchases?", response: "Digital purchases have a 15-day refund window. The code must remain unredeemed to receive a refund.", tool: "get_refund_policy", purpose: "Retrieve the backend's digital purchase refund policy.", outcome: "Returned the 15-day window and unredeemed-code requirement.", workflow: "refund_policy", operation: "read", model: true },
  { title: "Physical return eligibility", prompt: "Can I return my wireless headphones?", response: "In this example, your headphones are within the 30-day return window. To start the return and receive a label, use: Confirm start return and issue label.", tool: "get_refund_eligibility", purpose: "Read the backend-evaluated refund workflow for a physical order.", outcome: "The example order can enter return preparation; courier acceptance is required before refund issuance.", workflow: "physical_refund", operation: "eligibility", model: true },
  { title: "Digital refund confirmed", prompt: "Confirm invalidate code and issue refund", response: "Your digital code has been invalidated and the refund has been issued. The purchase now shows Refunded.", tool: "request_refund", purpose: "Invalidate the code after exact persisted confirmation is validated.", outcome: "Code invalidated and the digital purchase prepared for refund issuance.", workflow: "digital_refund", operation: "prepare_and_issue", model: false },
  { title: "Subscription refund confirmed", prompt: "Confirm cancel and issue refund", response: "Your subscription has been cancelled, automatic renewal is disabled, and the refund has been issued.", tool: "request_refund", purpose: "Cancel access and disable renewal after validated customer confirmation.", outcome: "Subscription cancelled and automatic renewal disabled; the purchase was prepared for refund issuance.", workflow: "subscription_refund", operation: "prepare_and_issue", model: false },
  { title: "Purchase lookup failed", prompt: "Could you check my recent purchases?", response: "I couldn’t retrieve your purchases at this time. Please try again shortly.", tool: "get_customer_purchase_history", purpose: "Read the selected customer's purchase history.", outcome: "The example database request timed out. No purchase facts were returned and no mutations were attempted.", workflow: "purchase_history", operation: "list", model: true, failed: true },
] as const;

export function buildDemoAuditSessions(referenceDate: string): readonly ModelAuditSessionDetail[] {
  const day = referenceDate.slice(0, 10);
  const anchor = Date.parse(`${day}T12:00:00Z`);
  if (!Number.isFinite(anchor)) throw new Error("Invalid demo audit reference date");
  return scenarios.map((scenario, index) => {
    const id = `demo-audit-${index + 1}`;
    const startedAt = new Date(anchor - index * 86_400_000).toISOString();
    const failed = "failed" in scenario && scenario.failed;
    const duration = scenario.model ? "2.4s" : "0.6s";
    const promptTokens = scenario.model ? 480 + index * 30 : 0;
    const completionTokens = scenario.model ? 120 + index * 10 : 0;
    const toolNames = scenario.model ? [scenario.tool] : [scenario.tool, "issue_refund"];
    const timestamp = (offset: number) => new Date(Date.parse(startedAt) + offset).toISOString();
    const steps = [
      { title: "Request received", category: "request", summary: scenario.prompt, offset: 0 },
      { title: "Customer context resolved", category: "context", summary: "The request was scoped to Avery Brooks and the selected workflow.", offset: 20 },
      ...(scenario.model ? [{ title: "Model read request", category: "model", summary: "The model requested a read-only tool within the backend-selected scope.", offset: 100 }] : [{ title: "Confirmation validated", category: "validation", summary: "The exact confirmation command and persisted consent were validated before any changes.", offset: 50 }]),
      ...toolNames.map((name, toolIndex) => ({ title: name === scenario.tool ? (failed ? "Tool request failed" : "Tool request completed") : name === "issue_refund" ? "Refund issued" : "Purchase state verified", category: scenario.model ? "tool" : name === "verify_purchase_state" ? "validation" : "mutation", summary: name === scenario.tool ? scenario.outcome : name === "issue_refund" ? "The guarded issuance operation recorded the refund in the example purchase." : "The final purchase and detail state matched the completed operation.", offset: scenario.model ? 1800 : 150 + toolIndex * 100 })),
      ...(!scenario.model ? [{ title: "Purchase state verified", category: "validation", summary: "The persisted purchase state matched the completed refund operation.", offset: 400 }] : []),
      { title: failed ? "Session failed" : "Response returned", category: "response", summary: scenario.response, offset: scenario.model ? 2400 : 600 },
    ];
    const timelineEvents = steps.map((step, stepIndex) => ({
      id: `${id}-event-${stepIndex + 1}`, sequenceNumber: stepIndex + 1,
      title: step.title, category: step.category, summary: step.summary,
      details: [{ label: "Customer", value: "Avery Brooks" }], occurredAt: timestamp(step.offset),
      status: failed && (step.category === "tool" || step.category === "response") ? "failed" : "completed",
      latency: null, tokenCount: step.category === "model" ? promptTokens + completionTokens : null,
      tokenCountIsEstimated: false, workflow: scenario.workflow, operation: scenario.operation,
      rawPayload: JSON.stringify({ simulated: true, sequence_number: stepIndex + 1, event_type: step.category, summary: step.summary, customer_id: mockCustomers[0].id }, null, 2),
    }));
    return {
      invocation: { id, startedAt, title: scenario.title, lastActive: new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" }).format(new Date(startedAt)), description: scenario.prompt, status: failed ? "failed" : "succeeded", eventCount: timelineEvents.length, toolCount: toolNames.length, failureCount: failed ? 1 : 0, totalTokens: promptTokens + completionTokens, latency: duration, timeToResponse: duration },
      modelName: scenario.model ? "Example model" : "Deterministic backend (no model call)", traceId: `${id}-trace`, requestId: `${id}-request`,
      metrics: { duration, workflowSteps: timelineEvents.length, modelCalls: scenario.model ? 1 : 0, toolCalls: toolNames.length, promptTokens, completionTokens, reasoningTokens: 0, totalTokens: promptTokens + completionTokens, estimatedInputTokens: toolNames.length * 48, estimatedOutputTokens: failed ? 0 : toolNames.length * 96, modelLatency: scenario.model ? "2.0s" : "0ms", toolLatency: scenario.model ? "0.2s" : "0.3s", workflowLatency: scenario.model ? "0.2s" : "0.3s" },
      prompt: scenario.prompt, finalResponse: scenario.response,
      toolCalls: toolNames.map((name, toolIndex) => ({ id: `${id}-tool-${toolIndex + 1}`, sequenceNumber: 4 + toolIndex, title: name, toolName: name, description: toolIndex === 0 ? scenario.purpose : name === "issue_refund" ? "Issue funds through a guarded backend operation after preparation." : "Read persisted purchase facts to verify the completed action.", summary: steps[3 + toolIndex].summary, occurredAt: timestamp(steps[3 + toolIndex].offset), status: failed ? "failed" : "completed", latency: "0.1s", source: scenario.model ? "model-requested read" : "deterministic backend", operation: scenario.operation, workflow: scenario.workflow, inputSummary: "Selected customer and workflow scope", outputSummary: steps[3 + toolIndex].summary, inputTokensEstimated: 48, outputTokensEstimated: failed ? 0 : 96, tokenizer: "Illustrative payload estimate", backendCategory: scenario.model ? "read" : name === "verify_purchase_state" ? "read" : "mutation", customerId: mockCustomers[0].id, purchaseId: null })),
      timelineEvents,
    };
  });
}
