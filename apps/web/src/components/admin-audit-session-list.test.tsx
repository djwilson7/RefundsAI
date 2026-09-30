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
  it("keeps tour records isolated from live reads, pagination, and streaming", () => {
    const eventSource = vi.fn();
    const observer = vi.fn();
    vi.stubGlobal("EventSource", eventSource);
    vi.stubGlobal("IntersectionObserver", observer);
    render(<AdminAuditSessionList tour initialHasMore={false} initialInvocations={[firstInvocation]} />);
    expect(eventSource).not.toHaveBeenCalled();
    expect(observer).not.toHaveBeenCalled();
    expect(getModelAuditInvocationPage).not.toHaveBeenCalled();
    expect(getModelAuditInvocation).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: /Can you check/ })).toHaveAttribute("href", `/admin/sessions/${firstInvocation.id}?tour=admin`);
  });
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

  it("shows the empty state when no sessions are available", () => {
    installIntersectionObserverMock();

    render(
      <AdminAuditSessionList
        initialHasMore={false}
        initialInvocations={[]}
      />,
    );

    expect(
      screen.getByText("No model invocations captured yet."),
    ).toBeInTheDocument();
  });

  it("repairs summary cards with missing original prompts after render", async () => {
    installIntersectionObserverMock();
    vi.mocked(getModelAuditInvocation).mockResolvedValue(firstInvocation);

    render(
      <AdminAuditSessionList
        initialHasMore={false}
        initialInvocations={[
          {
            ...firstInvocation,
            description: "Original prompt unavailable",
          },
        ]}
      />,
    );

    expect(screen.getByText("Original prompt unavailable")).toBeInTheDocument();
    expect(
      await screen.findByText(
        "Can you check whether my wireless headphones are eligible?",
      ),
    ).toBeInTheDocument();
    expect(getModelAuditInvocation).toHaveBeenCalledWith(firstInvocation.id);
  });

  it("reports a load error when the next page cannot be loaded", async () => {
    const observer = installIntersectionObserverMock();
    vi.mocked(getModelAuditInvocationPage).mockResolvedValue(null);

    render(
      <AdminAuditSessionList
        initialHasMore
        initialInvocations={[firstInvocation]}
      />,
    );

    observer.triggerIntersect();

    expect(
      await screen.findByText("Older audit sessions could not be loaded."),
    ).toBeInTheDocument();
  });

  it("ignores non-intersecting pagination updates", () => {
    const observer = installIntersectionObserverMock();

    render(
      <AdminAuditSessionList
        initialHasMore
        initialInvocations={[firstInvocation]}
      />,
    );

    observer.triggerNonIntersect();

    expect(getModelAuditInvocationPage).not.toHaveBeenCalled();
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

  it("ignores streamed events without a valid session update", async () => {
    vi.useFakeTimers();
    installIntersectionObserverMock();
    const eventSources = installEventSourceMock();
    vi.mocked(getModelAuditInvocation).mockResolvedValue(null);

    const { unmount } = render(
      <AdminAuditSessionList
        initialHasMore={false}
        initialInvocations={[firstInvocation]}
      />,
    );

    await act(async () => {
      eventSources[0].emit("model_audit_event", "{not-json");
      eventSources[0].emit("model_audit_event", JSON.stringify({ session_id: 123 }));
      eventSources[0].emit(
        "model_audit_event",
        JSON.stringify({ session_id: liveInvocation.id }),
      );
      await vi.advanceTimersByTimeAsync(250);
    });

    expect(
      screen.queryByText("A new customer just asked about a refund."),
    ).not.toBeInTheDocument();
    expect(getModelAuditInvocation).toHaveBeenCalledTimes(1);

    unmount();

    expect(eventSources[0].close).toHaveBeenCalledTimes(1);
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

  it("renders singular counts and non-success status labels", () => {
    installIntersectionObserverMock();

    render(
      <AdminAuditSessionList
        initialHasMore={false}
        initialInvocations={[
          {
            ...firstInvocation,
            status: "failed",
            eventCount: 1,
            toolCount: 1,
            failureCount: 1,
          },
          {
            ...olderInvocation,
            status: "running",
            failureCount: 2,
          },
        ]}
      />,
    );

    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("1 event")).toBeInTheDocument();
    expect(screen.getAllByText("1 tool")).toHaveLength(2);
    expect(screen.getByText("1 failure")).toBeInTheDocument();
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
    triggerNonIntersect: () => {
      callback?.([{ isIntersecting: false } as IntersectionObserverEntry]);
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
