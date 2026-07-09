import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AdminAuditLiveUpdates } from "./admin-audit-live-updates";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh,
  }),
}));

describe("AdminAuditLiveUpdates", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    refresh.mockReset();
  });

  it("does nothing when server-sent events are unavailable", () => {
    vi.stubGlobal("EventSource", undefined);

    render(<AdminAuditLiveUpdates />);

    expect(refresh).not.toHaveBeenCalled();
  });

  it("refreshes the route after debounced audit events", async () => {
    vi.useFakeTimers();
    const eventSources = installEventSourceMock();

    const { unmount } = render(<AdminAuditLiveUpdates />);

    expect(eventSources[0].url).toBe("/api/admin/audit/events/stream");

    await act(async () => {
      eventSources[0].emit("model_audit_event");
      eventSources[0].emit("model_audit_event");
      await vi.advanceTimersByTimeAsync(249);
    });

    expect(refresh).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });

    expect(refresh).toHaveBeenCalledTimes(1);

    unmount();

    expect(eventSources[0].removedType).toBe("model_audit_event");
    expect(eventSources[0].close).toHaveBeenCalledTimes(1);
  });

  it("streams only the requested session when a session id is provided", () => {
    const eventSources = installEventSourceMock();

    render(<AdminAuditLiveUpdates sessionId="session id/with spaces" />);

    expect(eventSources[0].url).toBe(
      "/api/admin/audit/events/stream?session_id=session%20id%2Fwith%20spaces",
    );
  });
});

function installEventSourceMock() {
  const instances: FakeEventSource[] = [];

  class FakeEventSource {
    listener: (() => void) | null = null;
    removedType: string | null = null;

    constructor(readonly url: string) {
      instances.push(this);
    }

    addEventListener(type: string, listener: () => void) {
      if (type === "model_audit_event") {
        this.listener = listener;
      }
    }

    removeEventListener(type: string) {
      this.removedType = type;
      this.listener = null;
    }

    close = vi.fn();

    emit(type: string) {
      if (type === "model_audit_event") {
        this.listener?.();
      }
    }
  }

  vi.stubGlobal("EventSource", FakeEventSource);

  return instances;
}
