import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AdminSessionDetailPage } from "./admin-session-detail-page";
import type { ModelAuditSessionDetail } from "@/lib/application-api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: vi.fn(),
  }),
}));

const detail: ModelAuditSessionDetail = {
  invocation: {
    id: "70000000-0000-4000-8000-000000000001",
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
  },
  modelName: "gpt-5.4-mini",
  traceId: "71000000-0000-4000-8000-000000000001",
  requestId: "req-123",
  metrics: {
    duration: "3.2s",
    workflowSteps: 14,
    modelCalls: 2,
    toolCalls: 1,
    promptTokens: 500,
    completionTokens: 312,
    reasoningTokens: 0,
    totalTokens: 812,
    estimatedInputTokens: 1_240,
    estimatedOutputTokens: 312,
    modelLatency: "2.4s",
    toolLatency: "18ms",
    workflowLatency: "3.2s",
  },
  prompt:
    "Can you check whether my wireless headphones are eligible for a refund?",
  finalResponse: "Yes, the purchase is eligible for a refund.",
  toolCalls: [
    {
      id: "73000000-0000-4000-8000-000000000002",
      sequenceNumber: 6,
      title: "Tool completed",
      toolName: "get_refund_eligibility",
      summary: "Backend refund-eligibility tool completed.",
      occurredAt: "4:18:01 PM",
      status: "completed",
      latency: "18ms",
      source: "deterministic_backend",
      operation: "get_refund_eligibility",
      workflow: "refund_eligibility",
      inputSummary: "2 recorded fields",
      outputSummary: "1 policy result",
      inputTokensEstimated: 12,
      outputTokensEstimated: 180,
      tokenizer: "tiktoken:cl100k_base",
      backendCategory: "backend_validation",
      customerId: "20000000-0000-4000-8000-000000000001",
      purchaseId: "40000000-0000-4000-8000-000000000001",
    },
  ],
  timelineEvents: [
    {
      id: "73000000-0000-4000-8000-000000000001",
      sequenceNumber: 1,
      title: "Request received",
      category: "request",
      summary:
        'Received customer request: "Can you check whether my wireless headphones are eligible for a refund?"',
      details: [
        {
          label: "Input / Customer Id",
          value: "20000000-0000-4000-8000-000000000001",
        },
      ],
      occurredAt: "4:18:00 PM",
      status: null,
      latency: null,
      tokenCount: null,
      workflow: null,
      operation: null,
      rawPayload: null,
    },
  ],
};

describe("AdminSessionDetailPage", () => {
  it("renders prompt, model response, tool history, and timeline", () => {
    render(
      <AdminSessionDetailPage
        detail={detail}
        sessionId="70000000-0000-4000-8000-000000000001"
      />,
    );

    expect(screen.getByText("Session Detail")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "User Prompt" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Can you check whether my wireless headphones are eligible for a refund?",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Model Response" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Tool History" }),
    ).toBeInTheDocument();
    expect(screen.getByText("gpt-5.4-mini")).toBeInTheDocument();
    expect(screen.getByText(detail.traceId)).toBeInTheDocument();
    expect(screen.getByText(detail.requestId)).toBeInTheDocument();
    expect(
      screen.getByText("Yes, the purchase is eligible for a refund."),
    ).toBeInTheDocument();
    expect(screen.getAllByText("get_refund_eligibility")).toHaveLength(2);
    expect(screen.getByText("Model Calls")).toBeInTheDocument();
    expect(screen.getByText("Reasoning Tokens")).toBeInTheDocument();
    expect(screen.getByText("Estimated Input Tokens")).toBeInTheDocument();
    expect(screen.getByText("1,240")).toBeInTheDocument();
    expect(screen.getByText("Input Tokens")).toBeInTheDocument();
    expect(screen.getByText("Output Tokens")).toBeInTheDocument();
    expect(screen.getByText("tiktoken:cl100k_base")).toBeInTheDocument();
    expect(screen.getAllByText("18ms")).toHaveLength(2);
    expect(screen.getByText("Request received")).toBeInTheDocument();
    expect(
      screen.getByText(
        'Received customer request: "Can you check whether my wireless headphones are eligible for a refund?"',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Input / Customer Id")).toBeInTheDocument();
  });

  it("renders an unavailable state when the session cannot be loaded", () => {
    render(
      <AdminSessionDetailPage
        detail={null}
        sessionId="70000000-0000-4000-8000-000000000404"
      />,
    );

    expect(screen.getByText("Audit session unavailable")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Session 70000000-0000-4000-8000-000000000404 could not be loaded from the audit API.",
      ),
    ).toBeInTheDocument();
  });
});
