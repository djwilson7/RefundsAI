"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { mockCustomers } from "./mock-customers";
import { storeSelectedMockCustomer } from "./mock-auth-session";
import { ProductHeader } from "./product-header";
import shellStyles from "./tour-shell.module.css";
import styles from "./technical-tour.module.css";

export function TechnicalTour() {
  const router = useRouter();
  const [startingClient, setStartingClient] = useState(false);

  function startClientTour() {
    const customer = mockCustomers[0];
    storeSelectedMockCustomer(customer);
    setStartingClient(true);
    router.push(`/user-home?customerId=${customer.id}&tour=client`);
  }

  return (
    <div className={`${shellStyles.page} ${styles.page}`}>
      <ProductHeader tour />
      <main className={styles.content}>
        <section className={styles.choices} aria-labelledby="tour-title">
          <header className={styles.intro}>
            <h1 id="tour-title">Choose your perspective.</h1>
            <p className={styles.summary}>Explore the experience from either side of the conversation.</p>
            <p className={styles.secondary}>You can swap perspectives at any point.</p>
          </header>
          <div className={styles.cards}>
            <article className={styles.card} aria-labelledby="client-title">
              <span className={styles.icon} aria-hidden="true">
                <svg viewBox="0 0 32 32" fill="none">
                  <circle cx="16" cy="11" r="5" />
                  <path d="M6 27v-3a10 10 0 0 1 20 0v3" />
                </svg>
              </span>
              <h2 id="client-title">Client</h2>
              <p>Let’s dive into how RefundsAI works for a customer who has made purchases in the past.</p>
              <button className={styles.start} type="button" onClick={startClientTour} disabled={startingClient} aria-label="Start client tour">
                {startingClient ? "Opening…" : "Begin Here"}
              </button>
            </article>
            <article className={`${styles.card} ${styles.adminCard}`} aria-labelledby="admin-title">
              <span className={styles.icon} aria-hidden="true">
                <svg viewBox="0 0 32 32" fill="none">
                  <rect x="5" y="5" width="22" height="22" rx="4" />
                  <path d="M10 21v-5m6 5V11m6 10v-8" />
                </svg>
              </span>
              <h2 id="admin-title">Admin</h2>
              <p>Explore how transparency is built into RefundsAI, giving admins a view of performance and the model’s actions.</p>
              <Link className={styles.start} href="/admin-home?tour=admin" aria-label="Start admin tour">
                Begin Here
              </Link>
            </article>
          </div>
        </section>
      </main>
    </div>
  );
}
