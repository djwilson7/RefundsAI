import styles from "./product-landing.module.css";
import { SmoothScrollLink } from "./smooth-scroll-link";
import { ProductHeader } from "./product-header";

const refundTypes = [
  { type: "Digital", signal: "Non-redeemed license", action: "Invalidate license", outcome: "Funds issued immediately", tone: "digitalRow" },
  { type: "Physical", signal: "Shipping status", action: "Carrier received", outcome: "Funds after handoff", tone: "physicalRow" },
  { type: "Subscription", signal: "Billing period + usage", action: "Cancel renewal + end service", outcome: "Full or prorated amount", tone: "subscriptionRow" },
] as const;

const integrationPoints = ["Commerce", "Customer context", "Policy", "Entitlements", "Payments", "Audit"] as const;

const governedSystems = [
  { name: "Customer context", role: "Read" },
  { name: "Policy engine", role: "Evaluate" },
  { name: "Entitlements", role: "Prepare" },
  { name: "Payment rail", role: "Execute" },
] as const;

const auditEvents = [
  { event: "User request received", detail: "Message and active purchase context captured.", owner: "Customer" },
  { event: "Intent interpreted + tools mapped", detail: "Model resolves the request and selects narrow capabilities.", owner: "Model" },
  { event: "Tools called", detail: "Model requests purchase, policy, and eligibility facts.", owner: "Model → tools" },
  { event: "Backend gates + result verified", detail: "Policy, consent, and authoritative state determine what is allowed.", owner: "Backend" },
  { event: "User informed", detail: "Model explains the verified state and what happens next.", owner: "Model" },
] as const;

export function ProductLanding() {
  return (
    <main className={styles.page}>
      <div className={styles.ambient} aria-hidden="true">
        <span className={styles.orbPrimary} />
        <span className={styles.orbSecondary} />
        <span className={styles.grid} />
      </div>

      <ProductHeader />

      <section className={styles.hero} id="top">
        <div className={styles.heroCopy}>
          <h1 aria-label="Refunds, governed.">Refunds,<span> governed.</span></h1>
          <p className={styles.heroSummary}>
            Resolve more refund requests without letting a model decide policy,
            authorize money, or mutate customer state.
          </p>
          <div className={styles.heroActions}>
            <SmoothScrollLink className={styles.primaryAction} href="#platform">
              <span>Explore<span className={styles.actionLongLabel}> the architecture</span></span>
              <span aria-hidden="true">↓</span>
            </SmoothScrollLink>
          </div>
        </div>
        <ProductPreview />
      </section>

      <section className={styles.entryCarousel} aria-label="Integration entry points">
        <strong className={styles.entryTitle}>Across your stack</strong>
        <div className={styles.entryViewport}>
          <div className={styles.entryTrack}>
            {[0, 1, 2].map((group) => (
              <div className={styles.entryGroup} aria-hidden={group > 0} key={group}>
                {integrationPoints.map((point) => (
                  <span key={point}><i aria-hidden="true" />{point}</span>
                ))}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.orchestrationSection} id="platform">
        <div className={styles.sectionIntro}>
          <h2>Connect once. Govern every refund path.</h2>
          <p>RefundsAI delegates to the systems that already own customer facts, policy, entitlements, and money.</p>
        </div>
        <div className={styles.orchestrationMap} aria-label="RefundsAI orchestration model">
          <div className={styles.sourceNodes}>
            <p className={styles.mapSideLabel}>Client</p>
            <span>Customer request</span>
            <span>Support channel</span>
          </div>
          <div className={styles.inboundLine} aria-hidden="true"><span>context</span></div>
          <div className={styles.orchestrationHub}>
            <LockMark />
            <span>RefundsAI</span>
            <strong>Interpret · route · explain</strong>
          </div>
          <div className={styles.permissionLine} aria-hidden="true">
            <span>request</span>
            <span>verified result</span>
          </div>
          <div className={styles.systemNodes}>
            <p className={styles.mapSideLabel}>Services</p>
            {governedSystems.map((system) => (
              <div key={system.name}><span>{system.name}</span><strong>{system.role}</strong></div>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.refundSection}>
        <div className={styles.sectionIntro}>
          <h2>Different products. Different paths.</h2>
          <p>One conversational surface adapts to the operational reality behind each refund.</p>
        </div>
        <div className={styles.refundMatrix}>
          <div className={styles.matrixHeader} aria-hidden="true">
            <span><strong>Product lifecycle</strong><small>What is being returned</small></span>
            <span><strong>Decision input</strong><small>Facts the backend trusts</small></span>
            <span><strong>Required transition</strong><small>State change before funds</small></span>
            <span><strong>Refund result</strong><small>How the path completes</small></span>
          </div>
          {refundTypes.map((refund) => (
            <article className={`${styles.refundRow} ${styles[refund.tone]}`} key={refund.type}>
              <div className={styles.refundType}>
                <span className={styles.mobileFieldLabel}>Purchase type</span>
                <span className={styles.typeMark} aria-hidden="true" />
                <strong>{refund.type}</strong>
              </div>
              <p data-label="Decision input">{refund.signal}</p>
              <p data-label="Required transition">{refund.action}</p>
              <p data-label="Refund result">{refund.outcome}</p>
            </article>
          ))}
        </div>
        <div className={styles.expansionNote}>
          <strong>Beyond refunds</strong>
          <span>Returns</span><i />
          <span>Cancellations</span><i />
          <span>Credits</span><i />
          <span>Exchanges</span>
        </div>
      </section>

      <section className={styles.workflowSection} id="workflow">
        <div className={styles.sectionIntro}>
          <h2>Flexible language. Fixed control.</h2>
        </div>
        <div className={styles.authorityVisual}>
          <article className={styles.aiDomain}>
            <div className={styles.domainHeader}><span>Model layer</span><strong>Flexible</strong></div>
            <div className={styles.domainPoint}><span>Interpret</span><p>Turn customer language into a scoped request.</p></div>
            <div className={styles.domainPoint}><span>Explain</span><p>Translate verified outcomes into clear support.</p></div>
          </article>
          <div className={styles.boundaryGate}>
            <LockMark />
            <strong>Authority gate</strong>
          </div>
          <article className={styles.backendDomain}>
            <div className={styles.domainHeader}><span>Backend control</span><strong>Authoritative</strong></div>
            <div className={styles.domainPoint}><span>Decide</span><p>Evaluate policy against persisted facts.</p></div>
            <div className={styles.domainPoint}><span>Execute</span><p>Authorize and verify every state change.</p></div>
          </article>
        </div>
      </section>

      <section className={styles.adminSection} id="controls">
        <div className={styles.sectionIntro}>
          <h2>Every handoff stays visible.</h2>
          <p>Operators can see what the model interpreted, what the backend decided, and where authority changed hands.</p>
        </div>
        <div className={styles.adminGrid}>
          <article className={styles.auditConsole}>
            <header>
              <div><span>Logged request lifecycle</span><strong>Refund case · ORD-10482</strong></div>
              <span className={styles.verifiedState}>Verified</span>
            </header>
            <ol aria-label="Logged request lifecycle">
              {auditEvents.map((item, index) => (
                <li key={item.event}>
                  <span className={styles.auditIndex}>0{index + 1}</span>
                  <i aria-hidden="true" />
                  <div className={styles.auditEventCopy}>
                    <strong>{item.event}</strong>
                    <small>{item.detail}</small>
                  </div>
                  <span>{item.owner}</span>
                </li>
              ))}
            </ol>
          </article>
          <div className={styles.adminBenefits}>
            <article>
              <span className={styles.cardLabel}>Authorization gate</span>
              <h3>Consent is scoped, verified, and consumed once.</h3>
              <p>No ambiguous approval becomes a financial action.</p>
            </article>
            <article className={styles.costCard}>
              <span className={styles.cardLabel}>Efficient by design</span>
              <h3>Fewer tokens. Lower latency. Lower operating cost.</h3>
              <div className={styles.costPaths} aria-label="Execution path comparison">
                <div><span>Open-ended request</span><i /><strong>Model + tools</strong></div>
                <div><span>Verified action</span><i /><strong>Backend only</strong></div>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.integrationClose}>
        <h2>Keep your systems. Add the control layer.</h2>
        <p>Narrow contracts connect the conversation to the systems of record you already trust.</p>
        <div className={styles.closePath} aria-label="Integration path">
          <div><span>Client</span><strong>Your channels</strong></div>
          <i aria-hidden="true">→</i>
          <div className={styles.closeCore}><span>Control layer</span><strong>RefundsAI</strong></div>
          <i aria-hidden="true">→</i>
          <div><span>Services</span><strong>Your systems of record</strong></div>
        </div>
      </section>

      <footer className={styles.footer}>
        <a className={styles.footerBrand} href="#top" aria-label="RefundsAI home"><LockMark /><span>RefundsAI</span></a>
        <div className={styles.footerCopy}>
          <p>Policy-governed refund automation.</p>
          <span>Concept product · Technical case study</span>
        </div>
      </footer>
    </main>
  );
}

function ProductPreview() {
  return (
    <aside className={styles.productPreview} aria-label="RefundsAI refund workspace preview">
      <header className={styles.previewHeader}>
        <div className={styles.previewWindowDots} aria-hidden="true"><span /><span /><span /></div>
        <span>Refund case · ORD-10482</span>
        <span className={styles.eligibleBadge}>Eligible</span>
      </header>
      <div className={styles.previewBody}>
        <div className={styles.conversationPane}>
          <span className={styles.paneLabel}>Customer conversation</span>
          <div className={styles.customerMessage}>I bought the photo editor yesterday. Can I get a refund?</div>
          <div className={styles.assistantMessage}>Your purchase is eligible for a full refund. Before funds can be issued, the unused license must be invalidated.</div>
          <div className={styles.confirmationBox}><span>Authorization gate</span><strong>Customer · Purchase · Permitted action</strong></div>
          <div className={styles.chatInput}>
            <span>Ask about this refund…</span>
            <button type="button" aria-label="Send message" disabled>↑</button>
          </div>
        </div>
        <div className={styles.decisionPane}>
          <span className={styles.paneLabel}>Policy decision</span>
          <div className={styles.decisionAmount}><span>Refundable amount</span><strong>$89.00</strong></div>
          <dl className={styles.decisionFacts}>
            <div><dt>Window</dt><dd>14 days left</dd></div>
            <div><dt>License</dt><dd>Unused</dd></div>
            <div><dt>Next action</dt><dd>Invalidate code</dd></div>
          </dl>
          <div className={styles.auditTrail}>
            <span>Execution evidence</span>
            <ol><li><i />Purchase resolved</li><li><i />Policy evaluated</li><li><i />Authorization gated</li></ol>
          </div>
        </div>
      </div>
    </aside>
  );
}

function LockMark() {
  return (
    <svg className={styles.lockMark} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <path d="M8 14.5V11a8 8 0 0 1 16 0v3.5" />
      <path d="M6.5 14.5h19v13h-19z" />
      <path d="M16 19v4" />
    </svg>
  );
}
