import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AdminHomePage } from "./admin-home-page";
import type { ModelAuditInvocation } from "@/lib/application-api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

const invocations: readonly ModelAuditInvocation[] = [
  {
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
  },
  {
    id: "70000000-0000-4000-8000-000000000002",
    startedAt: "2026-07-07T15:42:00Z",
    title: "July 7, 2026",
    lastActive: "Last active 3:42 PM",
    description:
      "What is the refund policy for subscription renewals after the first two days?",
    status: "succeeded",
    eventCount: 11,
    toolCount: 1,
    failureCount: 0,
    totalTokens: 684,
    latency: "2.5s",
    timeToResponse: "2.3s",
  },
  {
    id: "70000000-0000-4000-8000-000000000003",
    startedAt: "2026-07-06T17:09:00Z",
    title: "July 6, 2026",
    lastActive: "Last active 5:09 PM",
    description:
      "Start the return for the jacket order and send me the return label.",
    status: "failed",
    eventCount: 18,
    toolCount: 2,
    failureCount: 1,
    totalTokens: 1248,
    latency: "4.8s",
    timeToResponse: "4.4s",
  },
  {
    id: "70000000-0000-4000-8000-000000000004",
    startedAt: "2026-07-06T14:27:00Z",
    title: "July 6, 2026",
    lastActive: "Last active 2:27 PM",
    description:
      "Show me purchases from last month that were over one hundred dollars.",
    status: "running",
    eventCount: 12,
    toolCount: 1,
    failureCount: 0,
    totalTokens: 936,
    latency: "2.9s",
    timeToResponse: "2.7s",
  },
];

describe("AdminHomePage", () => {
  it("renders the shared admin home header", () => {
    render(<AdminHomePage hasMoreInvocations={false} invocations={invocations} />);

    expect(
      screen.getByText("Agentic Refund Model History"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "System Administrator",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Model performance and audit session review"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Log out" }),
    ).toBeInTheDocument();
  });

  it("renders model invocation cards with prompt descriptions and meta rows", () => {
    render(<AdminHomePage hasMoreInvocations={false} invocations={invocations} />);

    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Audit History",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 3, name: "July 7, 2026" }))
      .toHaveLength(2);
    expect(screen.getAllByRole("heading", { level: 3, name: "July 6, 2026" }))
      .toHaveLength(2);
    expect(
      screen.getByText("Last active 4:18 PM"),
    ).toBeInTheDocument();
    expect(screen.getByText("Last active 2:27 PM")).toBeInTheDocument();
    expect(screen.getAllByText("View Session")).toHaveLength(4);
    expect(
      screen.getByRole("link", {
        name: /Can you check whether my wireless headphones are eligible/u,
      }),
    ).toHaveAttribute(
      "href",
      "/admin/sessions/70000000-0000-4000-8000-000000000001",
    );
    expect(
      screen.getByText(
        "Can you check whether my wireless headphones are eligible for a refund?",
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByText("succeeded")).toHaveLength(2);
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("14 events")).toBeInTheDocument();
    expect(screen.getAllByText("1 tool")).toHaveLength(3);
    expect(screen.getByText("2 tools")).toBeInTheDocument();
    expect(screen.getAllByText("0 failures")).toHaveLength(3);
    expect(screen.getByText("1 failure")).toBeInTheDocument();
    expect(screen.getByText("812 tokens")).toBeInTheDocument();
    expect(screen.getByText("3.2s latency")).toBeInTheDocument();
    expect(screen.getByText("3.0s TTR")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Invocation metadata")).toHaveLength(4);
    expect(screen.queryByText("Tool Failures")).not.toBeInTheDocument();
    expect(screen.queryByText("Errors")).not.toBeInTheDocument();
    expect(screen.queryByText("Phase 5 Template Surface")).not.toBeInTheDocument();
    expect(screen.queryByText("Session Memory")).not.toBeInTheDocument();
    expect(screen.queryByText("Template")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Latest event summary placeholder/u),
    ).not.toBeInTheDocument();
  });

  it("renders an empty state when no model invocations are available", () => {
    render(<AdminHomePage hasMoreInvocations={false} invocations={[]} />);

    expect(
      screen.getByText("No model invocations captured yet."),
    ).toBeInTheDocument();
  });
});
