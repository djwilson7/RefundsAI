import type { ModelAuditInvocation } from "./application-api";

export function summarizeAuditInvocations(invocations: readonly ModelAuditInvocation[]) {
  const averageCount = (select: (item: ModelAuditInvocation) => number) =>
    invocations.length ? (invocations.reduce((sum, item) => sum + select(item), 0) / invocations.length).toFixed(1) : "—";

  // Audit durations arrive as display strings; unavailable values are not zero.
  const averageDuration = (select: (item: ModelAuditInvocation) => string) => {
    const durations = invocations.flatMap((item) => {
      const match = select(item).trim().match(/^(\d+(?:\.\d+)?)\s*(ms|s)$/);
      return match ? [Number(match[1]) * (match[2] === "ms" ? 1 : 1000)] : [];
    });
    if (!durations.length) return "—";
    return `${(durations.reduce((sum, value) => sum + value, 0) / durations.length / 1000).toFixed(2)}s`;
  };

  return {
    sessions: invocations.length,
    succeeded: invocations.filter((item) => item.status === "succeeded").length,
    failed: invocations.filter((item) => item.status === "failed").length,
    totalTokens: invocations.reduce((sum, item) => sum + item.totalTokens, 0),
    averageEvents: averageCount((item) => item.eventCount),
    averageTools: averageCount((item) => item.toolCount),
    averageLatency: averageDuration((item) => item.latency),
    averageTtr: averageDuration((item) => item.timeToResponse),
  };
}
