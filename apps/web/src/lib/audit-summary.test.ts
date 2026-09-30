import { describe, expect, it } from "vitest";
import { summarizeAuditInvocations } from "./audit-summary";
import { buildDemoAuditSessions } from "./demo-audit";

const invocations = buildDemoAuditSessions("2026-09-30T12:00:00Z").map((session) => session.invocation);

describe("audit summary aggregates", () => {
  it("includes every session, including failures and zero-token confirmations", () => {
    expect(summarizeAuditInvocations(invocations)).toEqual({
      sessions: 6, succeeded: 5, failed: 1, totalTokens: 2720,
      averageEvents: "5.7", averageTools: "1.3", averageLatency: "1.80s", averageTtr: "1.80s",
    });
  });
  it("normalizes mixed duration units and excludes unavailable durations", () => {
    const rows = [
      { ...invocations[0], latency: "500ms", timeToResponse: "1s" },
      { ...invocations[1], latency: "1.5s", timeToResponse: "—" },
    ];
    expect(summarizeAuditInvocations(rows).averageLatency).toBe("1.00s");
    expect(summarizeAuditInvocations(rows).averageTtr).toBe("1.00s");
  });
  it("shows unavailable averages instead of fabricated zero values for an empty history", () => {
    expect(summarizeAuditInvocations([])).toEqual({
      sessions: 0, succeeded: 0, failed: 0, totalTokens: 0,
      averageEvents: "—", averageTools: "—", averageLatency: "—", averageTtr: "—",
    });
  });
});
