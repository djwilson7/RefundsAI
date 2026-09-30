import { describe, expect, it } from "vitest";
import { buildDemoAuditSessions } from "./demo-audit";

describe("generated admin tour audits", () => {
  it("rebuilds stable complete records relative to the current day", () => {
    const sessions = buildDemoAuditSessions("2026-09-30T17:00:00Z");
    const next = buildDemoAuditSessions("2026-10-01T17:00:00Z");
    expect(sessions).toHaveLength(6);
    sessions.forEach((session, index) => {
      expect(session.invocation.id).toBe(next[index].invocation.id);
      expect(Date.parse(next[index].invocation.startedAt) - Date.parse(session.invocation.startedAt)).toBe(86_400_000);
      expect(session.invocation.eventCount).toBe(session.timelineEvents.length);
      expect(session.invocation.toolCount).toBe(session.toolCalls.length);
      expect(session.timelineEvents.map((event) => event.sequenceNumber)).toEqual(session.timelineEvents.map((_, i) => i + 1));
      expect(session.timelineEvents.every((event) => JSON.parse(event.rawPayload!).simulated)).toBe(true);
    });
  });
  it("separates model usage from deterministic actions and includes a terminal failure", () => {
    const sessions = buildDemoAuditSessions("2026-09-30T17:00:00Z");
    const confirmations = sessions.filter((session) => session.metrics.modelCalls === 0);
    expect(confirmations).toHaveLength(2);
    confirmations.forEach((session) => {
      expect(session.metrics.totalTokens).toBe(0);
      expect(session.metrics.estimatedInputTokens).toBeGreaterThan(0);
      expect(session.toolCalls.map((tool) => tool.toolName)).toContain("issue_refund");
    });
    expect(sessions.at(-1)?.invocation.status).toBe("failed");
    expect(sessions.at(-1)?.toolCalls[0].status).toBe("failed");
  });
});
