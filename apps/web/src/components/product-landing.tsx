import styles from "./product-landing.module.css";

const integrationSteps = [
  {
    number: "01",
    title: "Connect existing commerce data",
    description:
      "Bring customer, order, entitlement, delivery, and subscription facts into a narrow backend integration layer.",
  },
  {
    number: "02",
    title: "Encode policy as deterministic rules",
    description:
      "Keep eligibility, refund amounts, and lifecycle transitions in testable services instead of model prompts.",
  },
  {
    number: "03",
    title: "Automate with explicit boundaries",
    description:
      "Use AI for interpretation and explanation while confirmation gates and transactional systems retain authority.",
  },
] as const;

const architectureLayers = [
  {
    label: "Conversation",
    title: "AI understands the request",
    description: "Natural-language context, narrow read tools, and grounded explanations.",
  },
  {
    label: "Decision",
    title: "Backend policy decides",
    description: "Deterministic eligibility, exact consent, and guarded workflow transitions.",
  },
  {
    label: "Evidence",
    title: "Every step stays visible",
    description: "Ordered model, tool, validation, and mutation records for operational review.",
  },
] as const;

export function ProductLanding() {
  return (
    <main className={styles.page}>
      <div className={styles.ambient} aria-hidden="true">
        <span className={styles.orbPrimary} />
        <span className={styles.orbSecondary} />
        <span className={styles.grid} />
      </div>

      <nav className={styles.nav} aria-label="Primary navigation">
        <a className={styles.brand} href="#top" aria-label="RefundsAI home">
          <span className={styles.brandMark} aria-hidden="true">
            R
          </span>
          <span>RefundsAI</span>
        </a>
        <button
          className={styles.tourButton}
          disabled
          title="The technical tour is coming in the next demo pass."
          type="button"
        >
          Technical tour
          <span>Coming soon</span>
        </button>
      </nav>

      <section className={styles.hero} id="top">
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}>Policy-governed support automation</p>
          <h1>Refund conversations with transactional boundaries.</h1>
          <p className={styles.heroSummary}>
            RefundsAI helps customers navigate complex refund workflows while
            deterministic services keep control of policy, consent, amounts, and
            lifecycle changes.
          </p>
          <div className={styles.proofRow} aria-label="Product principles">
            <span>Grounded responses</span>
            <span>Guarded execution</span>
            <span>Complete audit trail</span>
          </div>
        </div>

        <aside className={styles.heroPanel} aria-label="RefundsAI operating model">
          <div className={styles.panelHeader}>
            <span className={styles.statusDot} />
            <span>Operating model</span>
            <span className={styles.panelStatus}>Bounded</span>
          </div>
          <div className={styles.flow}>
            <div>
              <span>Customer</span>
              <strong>Asks naturally</strong>
            </div>
            <span className={styles.flowLine} aria-hidden="true" />
            <div>
              <span>AI assistant</span>
              <strong>Interprets &amp; explains</strong>
            </div>
            <span className={styles.flowLine} aria-hidden="true" />
            <div>
              <span>Backend</span>
              <strong>Decides &amp; verifies</strong>
            </div>
          </div>
          <p className={styles.panelNote}>
            The model can guide the workflow. It cannot invent eligibility or
            authorize a financial transition.
          </p>
        </aside>
      </section>

      <section className={styles.section} aria-labelledby="commercial-integration">
        <div className={styles.sectionHeading}>
          <p className={styles.eyebrow}>Commercial integration</p>
          <h2 id="commercial-integration">
            Designed to sit between support conversations and systems of record.
          </h2>
          <p>
            The architecture complements existing commerce, CRM, entitlement, and
            payment infrastructure instead of replacing it.
          </p>
        </div>

        <div className={styles.cardGrid}>
          {integrationSteps.map((step) => (
            <article className={styles.glassCard} key={step.number}>
              <span className={styles.cardNumber}>{step.number}</span>
              <h3>{step.title}</h3>
              <p>{step.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.architecture} aria-labelledby="architecture-heading">
        <div className={styles.sectionHeading}>
          <p className={styles.eyebrow}>A deliberate separation of authority</p>
          <h2 id="architecture-heading">Flexible at the edge. Strict at the core.</h2>
        </div>
        <div className={styles.layerGrid}>
          {architectureLayers.map((layer) => (
            <article className={styles.layer} key={layer.label}>
              <span>{layer.label}</span>
              <h3>{layer.title}</h3>
              <p>{layer.description}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className={styles.footer}>
        <span>RefundsAI</span>
        <p>A bounded AI architecture for policy-sensitive customer support.</p>
      </footer>
    </main>
  );
}
