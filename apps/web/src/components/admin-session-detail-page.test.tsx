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
    },
  ],
  timelineEvents: [
    {
      id: "73000000-0000-4000-8000-000000000001",
      sequenceNumber: 1,
      title: "Request received",
      category: "request",
      summary: "FastAPI chat route received validated customer message.",
      occurredAt: "4:18:00 PM",
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
      screen.getByText(
        "Can you check whether my wireless headphones are eligible for a refund?",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("gpt-5.4-mini")).toBeInTheDocument();
    expect(
      screen.getByText("Yes, the purchase is eligible for a refund."),
    ).toBeInTheDocument();
    expect(screen.getByText("get_refund_eligibility")).toBeInTheDocument();
    expect(screen.getByText("Request received")).toBeInTheDocument();
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
