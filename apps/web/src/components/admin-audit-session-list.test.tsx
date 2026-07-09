import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AdminAuditSessionList } from "./admin-audit-session-list";
import type { ModelAuditInvocation } from "@/lib/application-api";
import {
  getModelAuditInvocation,
  getModelAuditInvocationPage,
} from "@/lib/application-api";

vi.mock("@/lib/application-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/application-api")>(
    "@/lib/application-api",
  );

  return {
    ...actual,
    getModelAuditInvocation: vi.fn(),
    getModelAuditInvocationPage: vi.fn(),
  };
});

const firstInvocation = buildInvocation({
  id: "70000000-0000-4000-8000-000000000001",
  prompt: "Can you check whether my wireless headphones are eligible?",
  startedAt: "2026-07-07T16:18:00Z",
});
const olderInvocation = buildInvocation({
  id: "70000000-0000-4000-8000-000000000002",
  prompt: "Show older refund policy activity.",
  startedAt: "2026-07-07T15:18:00Z",
});
const liveInvocation = buildInvocation({
  id: "70000000-0000-4000-8000-000000000003",
  prompt: "A new customer just asked about a refund.",
  startedAt: "2026-07-07T17:18:00Z",
});

describe("AdminAuditSessionList", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.mocked(getModelAuditInvocation).mockReset();
    vi.mocked(getModelAuditInvocationPage).mockReset();
  });

  it("loads the next page when the bottom sentinel intersects", async () => {
    const observer = installIntersectionObserverMock();
    vi.mocked(getModelAuditInvocationPage).mockResolvedValue({
      hasMore: false,
      invocations: [olderInvocation],
    });

    render(
      <AdminAuditSessionList
        initialHasMore
        initialInvocations={[firstInvocation]}
      />,
    );

    observer.triggerIntersect();

    expect(
      await screen.findByText("Show older refund policy activity."),
    ).toBeInTheDocument();
    expect(getModelAuditInvocationPage).toHaveBeenCalledWith({
      limit: 10,
      offset: 1,
    });
    expect(
      screen.getByText("All stored audit sessions loaded."),
    ).toBeInTheDocument();
  });

  it("inserts streamed session updates into the visible list", async () => {
    vi.useFakeTimers();
    installIntersectionObserverMock();
    const eventSources = installEventSourceMock();
    vi.mocked(getModelAuditInvocation).mockResolvedValue(liveInvocation);

    render(
      <AdminAuditSessionList
        initialHasMore={false}
        initialInvocations={[firstInvocation]}
      />,
    );

    await act(async () => {
      eventSources[0].emit(
        "model_audit_event",
        JSON.stringify({ session_id: liveInvocation.id }),
      );
      await vi.advanceTimersByTimeAsync(250);
    });

    expect(
      screen.getByText("A new customer just asked about a refund."),
    ).toBeInTheDocument();
    expect(vi.mocked(getModelAuditInvocation).mock.calls[0][0]).toBe(
      liveInvocation.id,
    );
    expect(screen.getAllByText("View Session")).toHaveLength(2);
  });

  it("shows zero actual tokens for deterministic workflows", () => {
    installIntersectionObserverMock();

    render(
      <AdminAuditSessionList
        initialHasMore={false}
        initialInvocations={[
          {
            ...firstInvocation,
            totalTokens: 0,
          },
        ]}
      />,
    );

    expect(screen.getByText("0 tokens")).toBeInTheDocument();
  });
});

function buildInvocation({
  id,
  prompt,
  startedAt,
}: {
  id: string;
  prompt: string;
  startedAt: string;
}): ModelAuditInvocation {
  return {
    id,
    startedAt,
    title: "July 7, 2026",
    lastActive: "Last active 4:18 PM",
    description: prompt,
    status: "succeeded",
    eventCount: 4,
    toolCount: 1,
    failureCount: 0,
    totalTokens: 120,
    latency: "1.2s",
    timeToResponse: "1.0s",
  };
}

function installIntersectionObserverMock() {
  let callback:
    | ((entries: IntersectionObserverEntry[]) => void)
    | null = null;
  const observe = vi.fn();
  const disconnect = vi.fn();

  class MockIntersectionObserver {
    constructor(nextCallback: (entries: IntersectionObserverEntry[]) => void) {
      callback = nextCallback;
    }

    observe = observe;
    disconnect = disconnect;
  }

  vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);

  return {
    triggerIntersect: () => {
      callback?.([{ isIntersecting: true } as IntersectionObserverEntry]);
    },
  };
}

function installEventSourceMock() {
  const instances: FakeEventSource[] = [];

  class FakeEventSource {
    listeners = new Map<string, (event: MessageEvent) => void>();

    constructor(readonly url: string) {
      instances.push(this);
    }

    addEventListener(type: string, listener: (event: MessageEvent) => void) {
      this.listeners.set(type, listener);
    }

    removeEventListener(type: string) {
      this.listeners.delete(type);
    }

    close = vi.fn();

    emit(type: string, data: string) {
      this.listeners.get(type)?.({ data } as MessageEvent);
    }
  }

  vi.stubGlobal("EventSource", FakeEventSource);

  return instances;
}
