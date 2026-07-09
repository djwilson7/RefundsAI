"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  getModelAuditInvocation,
  getModelAuditInvocationPage,
  type ModelAuditInvocation,
} from "@/lib/application-api";
import { ArrowRightIcon } from "./icons";
import styles from "./admin-home-page.module.css";

const auditSessionPageSize = 10;
const liveUpdateDebounceMs = 250;

type AdminAuditSessionListProps = Readonly<{
  initialHasMore: boolean;
  initialInvocations: readonly ModelAuditInvocation[];
}>;

export function AdminAuditSessionList({
  initialHasMore,
  initialInvocations,
}: AdminAuditSessionListProps) {
  const [invocations, setInvocations] = useState<readonly ModelAuditInvocation[]>(
    initialInvocations,
  );
  const [hasMore, setHasMore] = useState(initialHasMore);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const loadedPageCountRef = useRef(initialInvocations.length);
  const isLoadingMoreRef = useRef(false);
  const hasMoreRef = useRef(initialHasMore);

  useEffect(() => {
    isLoadingMoreRef.current = isLoadingMore;
  }, [isLoadingMore]);

  useEffect(() => {
    hasMoreRef.current = hasMore;
  }, [hasMore]);

  useEffect(() => {
    const missingPromptSessionIds = invocations
      .filter((invocation) => invocation.description === "Original prompt unavailable")
      .map((invocation) => invocation.id);

    if (missingPromptSessionIds.length === 0) {
      return;
    }

    let cancelled = false;

    void Promise.all(
      missingPromptSessionIds.map((sessionId) => getModelAuditInvocation(sessionId)),
    ).then((updates) => {
      if (cancelled) {
        return;
      }

      const repairedInvocations = updates.filter(
        (invocation): invocation is ModelAuditInvocation =>
          invocation !== null &&
          invocation.description !== "Original prompt unavailable",
      );

      if (repairedInvocations.length === 0) {
        return;
      }

      setInvocations((current) => {
        const merged = mergeInvocations(current, repairedInvocations);
        loadedPageCountRef.current = merged.length;

        return merged;
      });
    });

    return () => {
      cancelled = true;
    };
  }, [invocations]);

  const loadMoreInvocations = useCallback(async () => {
    if (isLoadingMoreRef.current || !hasMoreRef.current) {
      return;
    }

    isLoadingMoreRef.current = true;
    setIsLoadingMore(true);
    setLoadError(false);

    const page = await getModelAuditInvocationPage({
      limit: auditSessionPageSize,
      offset: loadedPageCountRef.current,
    });

    if (!page) {
      setLoadError(true);
      isLoadingMoreRef.current = false;
      setIsLoadingMore(false);
      return;
    }

    hasMoreRef.current = page.hasMore;
    setHasMore(page.hasMore);
    setInvocations((current) => {
      const merged = mergeInvocations(current, page.invocations);
      loadedPageCountRef.current = merged.length;

      return merged;
    });
    isLoadingMoreRef.current = false;
    setIsLoadingMore(false);
  }, []);

  useEffect(() => {
    const sentinel = sentinelRef.current;

    if (!sentinel || typeof IntersectionObserver === "undefined") {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) {
          return;
        }

        void loadMoreInvocations();
      },
      { rootMargin: "320px 0px" },
    );

    observer.observe(sentinel);

    return () => {
      observer.disconnect();
    };
  }, [loadMoreInvocations]);

  useEffect(() => {
    if (typeof EventSource === "undefined") {
      return;
    }

    let refreshTimer: ReturnType<typeof setTimeout> | null = null;
    const pendingSessionIds = new Set<string>();
    const eventSource = new EventSource("/api/admin/audit/events/stream");

    const flushSessionUpdates = () => {
      refreshTimer = null;
      const sessionIds = [...pendingSessionIds];
      pendingSessionIds.clear();

      void Promise.all(
        sessionIds.map((sessionId) => getModelAuditInvocation(sessionId)),
      ).then((updates) => {
        const nextInvocations = updates.filter(
          (invocation): invocation is ModelAuditInvocation => invocation !== null,
        );

        if (nextInvocations.length === 0) {
          return;
        }

        setInvocations((current) => {
          const merged = mergeInvocations(current, nextInvocations);
          loadedPageCountRef.current = merged.length;

          return merged;
        });
      });
    };

    const scheduleSessionUpdate = (event: MessageEvent) => {
      const sessionId = getSessionIdFromAuditEvent(event.data);

      if (!sessionId) {
        return;
      }

      pendingSessionIds.add(sessionId);

      if (refreshTimer !== null) {
        clearTimeout(refreshTimer);
      }

      refreshTimer = setTimeout(flushSessionUpdates, liveUpdateDebounceMs);
    };

    eventSource.addEventListener("model_audit_event", scheduleSessionUpdate);

    return () => {
      eventSource.removeEventListener("model_audit_event", scheduleSessionUpdate);
      eventSource.close();

      if (refreshTimer !== null) {
        clearTimeout(refreshTimer);
      }
    };
  }, []);

  if (invocations.length === 0) {
    return <p className={styles.emptyState}>No model invocations captured yet.</p>;
  }

  return (
    <>
      <div className={styles.sessionGrid}>
        {invocations.map((invocation) => (
          <AuditSessionCard invocation={invocation} key={invocation.id} />
        ))}
      </div>
      <div
        aria-label="Audit history pagination status"
        className={styles.paginationStatus}
        ref={sentinelRef}
        role="status"
      >
        {loadError ? "Older audit sessions could not be loaded." : null}
        {!loadError && isLoadingMore ? "Loading older audit sessions..." : null}
        {!loadError && !isLoadingMore && !hasMore
          ? "All stored audit sessions loaded."
          : null}
      </div>
    </>
  );
}

function AuditSessionCard({
  invocation,
}: Readonly<{ invocation: ModelAuditInvocation }>) {
  return (
    <Link
      className={styles.sessionCard}
      href={`/admin/sessions/${invocation.id}`}
    >
      <div className={styles.cardHeader}>
        <h3 className={styles.cardTitle}>{invocation.title}</h3>
        <span className={styles.actionSlot}>
          <time className={styles.lastActive}>{invocation.lastActive}</time>
          <span className={styles.viewSession}>
            <span>View Session</span>
            <ArrowRightIcon />
          </span>
        </span>
      </div>

      <p className={styles.description}>{invocation.description}</p>

      <div className={styles.metaRows} aria-label="Invocation metadata">
        <p className={styles.metaRow}>
          <span className={getStatusClassName(invocation.status)}>
            {invocation.status}
          </span>
          <span>{formatCount(invocation.eventCount, "event")}</span>
          <span>{formatCount(invocation.toolCount, "tool")}</span>
          <span>{formatCount(invocation.failureCount, "failure")}</span>
        </p>
        <p className={styles.metaRow}>
          <span>
            {invocation.totalTokens} tokens
          </span>
          <span>{invocation.latency} latency</span>
          <span>{invocation.timeToResponse} TTR</span>
        </p>
      </div>
    </Link>
  );
}

function mergeInvocations(
  current: readonly ModelAuditInvocation[],
  incoming: readonly ModelAuditInvocation[],
) {
  const byId = new Map<string, ModelAuditInvocation>();

  for (const invocation of current) {
    byId.set(invocation.id, invocation);
  }

  for (const invocation of incoming) {
    byId.set(invocation.id, invocation);
  }

  return [...byId.values()].sort(compareInvocations);
}

function compareInvocations(
  first: ModelAuditInvocation,
  second: ModelAuditInvocation,
) {
  const firstStarted = Date.parse(first.startedAt);
  const secondStarted = Date.parse(second.startedAt);

  if (Number.isNaN(firstStarted) || Number.isNaN(secondStarted)) {
    return 0;
  }

  return secondStarted - firstStarted;
}

function getSessionIdFromAuditEvent(data: string) {
  try {
    const parsed = JSON.parse(data) as { session_id?: unknown };

    return typeof parsed.session_id === "string" ? parsed.session_id : null;
  } catch {
    return null;
  }
}

function getStatusClassName(status: string) {
  if (status === "succeeded") {
    return styles.statusSucceeded;
  }

  if (status === "failed") {
    return styles.statusFailed;
  }

  if (status === "running") {
    return styles.statusRunning;
  }

  return undefined;
}

function formatCount(count: number, label: string) {
  return `${count} ${label}${count === 1 ? "" : "s"}`;
}
