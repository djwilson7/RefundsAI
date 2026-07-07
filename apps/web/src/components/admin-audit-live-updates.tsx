"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

const refreshDebounceMs = 250;

type AdminAuditLiveUpdatesProps = Readonly<{
  sessionId?: string;
}>;

export function AdminAuditLiveUpdates({ sessionId }: AdminAuditLiveUpdatesProps) {
  const router = useRouter();

  useEffect(() => {
    if (typeof EventSource === "undefined") {
      return;
    }

    let refreshTimer: ReturnType<typeof setTimeout> | null = null;
    const streamUrl = sessionId
      ? `/api/admin/audit/events/stream?session_id=${encodeURIComponent(sessionId)}`
      : "/api/admin/audit/events/stream";
    const eventSource = new EventSource(streamUrl);
    const scheduleRefresh = () => {
      if (refreshTimer !== null) {
        clearTimeout(refreshTimer);
      }

      refreshTimer = setTimeout(() => {
        router.refresh();
      }, refreshDebounceMs);
    };

    eventSource.addEventListener("model_audit_event", scheduleRefresh);

    return () => {
      eventSource.removeEventListener("model_audit_event", scheduleRefresh);
      eventSource.close();

      if (refreshTimer !== null) {
        clearTimeout(refreshTimer);
      }
    };
  }, [router, sessionId]);

  return null;
}
