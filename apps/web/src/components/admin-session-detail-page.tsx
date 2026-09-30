import Link from "next/link";
import { AdminAuditLiveUpdates } from "./admin-audit-live-updates";
import { AppCard } from "./app-card";
import type { ModelAuditSessionDetail } from "@/lib/application-api";
import styles from "./admin-session-detail-page.module.css";
import { ProductHeader } from "./product-header";
import shellStyles from "./tour-shell.module.css";
import { ArrowRightIcon } from "./icons";

type AdminSessionDetailPageProps = Readonly<{
  detail: ModelAuditSessionDetail | null;
  sessionId: string;
  tour?: boolean;
}>;

export function AdminSessionDetailPage({
  detail,
  sessionId,
  tour = false,
}: AdminSessionDetailPageProps) {
  if (!detail) {
    return (
      <main className={styles.page}>
        <AppCard className={styles.content}>
          <Link className={styles.backLink} href="/admin-home">
            Back to audit history
          </Link>
          <p className={styles.eyebrow}>Session Detail</p>
          <h1 className={styles.heading}>Audit session unavailable</h1>
          <p className={styles.summary}>
            Session {sessionId} could not be loaded from the audit API.
          </p>
        </AppCard>
      </main>
    );
  }

  return (
    <div className={tour ? shellStyles.page : undefined}>
      {tour ? <ProductHeader tour tourRole="admin" identityName="System Administrator" /> : null}
    <main className={`${styles.page} ${tour ? styles.tourPage : ""}`}>
      {!tour ? <AdminAuditLiveUpdates sessionId={detail.invocation.id} /> : null}
      {tour ? <div className={styles.topbar}>
        <Link className={styles.backIcon} href="/admin-home?tour=admin" aria-label="Back to audit history" title="Back to audit history"><ArrowRightIcon /></Link>
        <span>Simulated Audit Session</span>
      </div> : null}
      <AppCard className={styles.content}>
        {!tour ? <Link className={styles.backLink} href="/admin-home">
          Back to audit history
        </Link> : null}
        <p className={styles.eyebrow}>Session Detail</p>
        <div className={styles.header}>
          <div>
            <h1 className={styles.heading}>{detail.invocation.title}</h1>
          </div>
          <span className={getStatusClassName(detail.invocation.status)}>
            {detail.invocation.status}
          </span>
        </div>

        <dl className={styles.sessionSnapshot} aria-label="Session at a glance">
          <div><dt>Duration</dt><dd>{detail.metrics.duration}</dd></div>
          <div><dt>Events</dt><dd>{detail.invocation.eventCount}</dd></div>
          <div><dt>Tools</dt><dd>{detail.metrics.toolCalls}</dd></div>
          <div><dt>Model calls</dt><dd>{detail.metrics.modelCalls}</dd></div>
          <div><dt>Provider tokens</dt><dd>{detail.metrics.totalTokens.toLocaleString("en-US")}</dd></div>
          <div><dt>Failures</dt><dd>{detail.invocation.failureCount}</dd></div>
        </dl>
        <details className={styles.sessionMetadata} open={!tour}>
          <summary>Session metrics and identity</summary>
        <div className={styles.metaSections}>
          <section className={styles.metaSection} aria-labelledby="request-identity">
            <h2 className={styles.metaSectionTitle} id="request-identity">
              Request Identity
            </h2>
            <dl className={`${styles.metaGrid} ${styles.identityGrid}`}>
              <div>
                <dt>Model</dt>
                <dd>{detail.modelName}</dd>
              </div>
              <div>
                <dt>Trace ID</dt>
                <dd>{detail.traceId}</dd>
              </div>
              <div>
                <dt>Request ID</dt>
                <dd>{detail.requestId}</dd>
              </div>
            </dl>
          </section>

          <section className={styles.metaSection} aria-labelledby="process-metadata">
            <h2 className={styles.metaSectionTitle} id="process-metadata">
              Process Metadata
            </h2>
            <dl className={`${styles.metaGrid} ${styles.processGrid}`}>
              <div>
                <dt>Session Duration</dt>
                <dd>{detail.metrics.duration}</dd>
              </div>
              <div>
                <dt>Workflow Steps</dt>
                <dd>{detail.metrics.workflowSteps}</dd>
              </div>
              <div>
                <dt>Model Calls</dt>
                <dd>{detail.metrics.modelCalls}</dd>
              </div>
              <div>
                <dt>Tool Calls</dt>
                <dd>{detail.metrics.toolCalls}</dd>
              </div>
              <div>
                <dt>Model Latency</dt>
                <dd>{detail.metrics.modelLatency}</dd>
              </div>
              <div>
                <dt>Tool Latency</dt>
                <dd>{detail.metrics.toolLatency}</dd>
              </div>
              <div>
                <dt>Workflow Latency</dt>
                <dd>{detail.metrics.workflowLatency}</dd>
              </div>
            </dl>
          </section>

          <section className={styles.metaSection} aria-labelledby="token-usage">
            <h2 className={styles.metaSectionTitle} id="token-usage">
              Token Usage
            </h2>
            <div className={styles.tokenGroups}>
              <div className={styles.tokenGroup}>
                <h3>Actual</h3>
                <dl className={`${styles.metaGrid} ${styles.actualTokenGrid}`}>
                  <div>
                    <dt>Total</dt>
                    <dd>{detail.metrics.totalTokens.toLocaleString()}</dd>
                  </div>
                  <div>
                    <dt>Prompt</dt>
                    <dd>{detail.metrics.promptTokens.toLocaleString()}</dd>
                  </div>
                  <div>
                    <dt>Completion</dt>
                    <dd>{detail.metrics.completionTokens.toLocaleString()}</dd>
                  </div>
                  <div>
                    <dt>Reasoning</dt>
                    <dd>{detail.metrics.reasoningTokens.toLocaleString()}</dd>
                  </div>
                </dl>
              </div>
              <div className={styles.tokenGroup}>
                <h3>Estimated</h3>
                <dl className={`${styles.metaGrid} ${styles.estimatedTokenGrid}`}>
                  <div>
                    <dt>Input</dt>
                    <dd>
                      {detail.metrics.estimatedInputTokens.toLocaleString()}
                    </dd>
                  </div>
                  <div>
                    <dt>Output</dt>
                    <dd>
                      {detail.metrics.estimatedOutputTokens.toLocaleString()}
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
          </section>
        </div>
        </details>
      </AppCard>

      <div className={`${styles.section} ${styles.conversationGrid}`}>
      <section className={styles.conversationSection}>
        <h2 className={styles.sectionTitle}>User Prompt</h2>
        <article className={`${styles.panel} ${styles.promptPanel}`}>
          <p className={styles.responseText}>{detail.prompt}</p>
        </article>
      </section>

      <section className={styles.conversationSection}>
        <h2 className={styles.sectionTitle}>{tour && detail.metrics.modelCalls === 0 ? "Backend Response" : "Model Response"}</h2>
        <article className={`${styles.panel} ${styles.responsePanel}`}>
          <p className={styles.responseText}>{detail.finalResponse}</p>
        </article>
      </section>
      </div>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Tool History</h2>
        {detail.toolCalls.length > 0 ? (
          <div className={styles.toolGrid}>
            {detail.toolCalls.map((toolCall) => (
              <article className={styles.panel} key={toolCall.id}>
                <div className={styles.panelHeader}>
                  <h3>{tour ? readableToolName(toolCall.toolName) : toolCall.toolName}</h3>
                  <span>{toolCall.status}</span>
                </div>
                <p className={styles.toolPurpose}>{toolCall.description}</p>
                <p className={styles.toolOutcome}>
                  <strong>Recorded outcome:</strong> {toolCall.summary}
                </p>
                <details className={styles.inspectionDetails} open={!tour}>
                  <summary>Inspect tool details</summary>
                <dl className={styles.toolDetails}>
                  <div><dt>Tool</dt><dd>{toolCall.toolName}</dd></div>
                  <div><dt>Sequence</dt><dd>{toolCall.sequenceNumber}</dd></div>
                  <div><dt>Latency</dt><dd>{toolCall.latency}</dd></div>
                  <div><dt>Source</dt><dd>{toolCall.source}</dd></div>
                  <div><dt>Workflow</dt><dd>{toolCall.workflow}</dd></div>
                  <div><dt>Operation</dt><dd>{toolCall.operation}</dd></div>
                  <div><dt>Category</dt><dd>{toolCall.backendCategory}</dd></div>
                  {toolCall.inputTokensEstimated != null ? (
                    <div>
                      <dt>Input Tokens</dt>
                      <dd>{toolCall.inputTokensEstimated.toLocaleString()}</dd>
                    </div>
                  ) : null}
                  {toolCall.outputTokensEstimated != null ? (
                    <div>
                      <dt>Output Tokens</dt>
                      <dd>{toolCall.outputTokensEstimated.toLocaleString()}</dd>
                    </div>
                  ) : null}
                  {toolCall.tokenizer ? (
                    <div><dt>Tokenizer</dt><dd>{toolCall.tokenizer}</dd></div>
                  ) : null}
                  <div><dt>Input</dt><dd>{toolCall.inputSummary}</dd></div>
                  <div><dt>Output</dt><dd>{toolCall.outputSummary}</dd></div>
                  {toolCall.customerId ? (
                    <div><dt>Customer</dt><dd>{toolCall.customerId}</dd></div>
                  ) : null}
                  {toolCall.purchaseId ? (
                    <div><dt>Purchase</dt><dd>{toolCall.purchaseId}</dd></div>
                  ) : null}
                </dl>
                <p className={styles.timestamp}>{toolCall.occurredAt}</p>
                </details>
              </article>
            ))}
          </div>
        ) : (
          <p className={styles.emptyState}>No tool calls were recorded.</p>
        )}
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Execution Timeline</h2>
        <ol className={styles.timeline}>
          {detail.timelineEvents.map((event) => (
            <li className={styles.timelineItem} key={event.id}>
              <span className={styles.sequence}>{event.sequenceNumber}</span>
              <div>
                <div className={styles.timelineHeader}>
                  <h3>{event.title}</h3>
                  <span className={styles.eventStatus}>
                    <strong>Event Type</strong> {event.category}
                  </span>
                </div>
                <p>{event.summary}</p>
                <p className={styles.timestamp}>{eventTimeLabel(event.occurredAt, detail.invocation.startedAt)}</p>
                {event.details.length > 0 || event.latency || event.tokenCount !== null || event.workflow || event.operation || event.rawPayload || event.status ? (
                <details className={styles.inspectionDetails} open={!tour}>
                  <summary>Inspect event details</summary>
                  <p className={styles.eventLifecycle}>Recorded at: {event.occurredAt}</p>
                  {event.status ? <p className={styles.eventLifecycle}>Lifecycle status: {event.status}</p> : null}
                {event.details.length > 0 ? (
                  <dl className={styles.timelineDetails}>
                    {event.details.map((detail) => (
                      <div key={`${detail.label}-${detail.value}`}>
                        <dt>{detail.label}</dt>
                        <dd>{detail.value}</dd>
                      </div>
                    ))}
                  </dl>
                ) : null}
                {event.latency ||
                event.tokenCount !== null ||
                event.workflow ||
                event.operation ? (
                  <dl className={styles.eventContext} aria-label="Event context">
                    {event.latency ? (
                      <div>
                        <dt>Latency</dt>
                        <dd>{event.latency}</dd>
                      </div>
                    ) : null}
                    {event.tokenCount !== null ? (
                      <div>
                        <dt>
                          {event.tokenCountIsEstimated
                            ? "Estimated tokens"
                            : "Model tokens"}
                        </dt>
                        <dd>{event.tokenCount.toLocaleString()}</dd>
                      </div>
                    ) : null}
                    {event.workflow ? (
                      <div>
                        <dt>Workflow</dt>
                        <dd>{event.workflow}</dd>
                      </div>
                    ) : null}
                    {event.operation ? (
                      <div>
                        <dt>Operation</dt>
                        <dd>{event.operation}</dd>
                      </div>
                    ) : null}
                  </dl>
                ) : null}
                {event.rawPayload ? (
                  <details className={styles.payloadDetails}>
                    <summary>Recorded payload</summary>
                    <pre>{event.rawPayload}</pre>
                  </details>
                ) : null}
                </details>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      </section>
    </main>
    </div>
  );
}

function readableToolName(name: string) {
  const label = name.replaceAll("_", " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function eventTimeLabel(occurredAt: string, startedAt: string) {
  const elapsed = Date.parse(occurredAt) - Date.parse(startedAt);
  if (!Number.isFinite(elapsed) || elapsed < 0) return occurredAt;
  return elapsed < 1000 ? `+${elapsed}ms from session start` : `+${(elapsed / 1000).toFixed(2)}s from session start`;
}

function getStatusClassName(status: string) {
  if (status === "succeeded") {
    return `${styles.statusPill} ${styles.statusSucceeded}`;
  }

  if (status === "failed") {
    return `${styles.statusPill} ${styles.statusFailed}`;
  }

  if (status === "running") {
    return `${styles.statusPill} ${styles.statusRunning}`;
  }

  return styles.statusPill;
}
