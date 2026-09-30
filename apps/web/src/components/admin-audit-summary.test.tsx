import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AdminAuditSummary } from "./admin-audit-summary";
import { buildDemoAuditSessions } from "@/lib/demo-audit";

describe("AdminAuditSummary", () => {
  it("groups outcomes together and renders overall performance metrics", () => {
    render(<AdminAuditSummary invocations={buildDemoAuditSessions("2026-09-30T12:00:00Z").map((session) => session.invocation)} />);
    const outcomes = screen.getByText("Session Outcomes").parentElement!;
    expect(within(outcomes).getByText("Success")).toBeInTheDocument();
    expect(within(outcomes).getByText("5")).toBeInTheDocument();
    expect(within(outcomes).getByText("Failure")).toBeInTheDocument();
    expect(within(outcomes).getByText("1")).toBeInTheDocument();
    expect(screen.getByText("Total Token Usage").parentElement).toHaveTextContent("2,720");
    expect(screen.getByText("Avg. Events").parentElement).toHaveTextContent("5.7");
    expect(screen.getByText("Avg. Tool Calls").parentElement).toHaveTextContent("1.3");
    expect(screen.getByText("Avg. Latency").parentElement).toHaveTextContent("1.80s");
    expect(screen.getByText("Avg. Time to Response").parentElement).toHaveTextContent("1.80s");
    expect(screen.queryByText("Example Model Tokens")).not.toBeInTheDocument();
  });
});
