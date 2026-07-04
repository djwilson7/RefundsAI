"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AppCard } from "./app-card";
import { storeSelectedMockCustomer } from "./mock-auth-session";
import {
  buildMockCredentials,
  getRandomMockCustomer,
  mockAdmin,
  type MockCredentials,
  type MockIdentity,
} from "./mock-customers";
import styles from "./mock-auth-landing.module.css";

const fillAnimationStepDelayMs = 28;
const loginTransitionDelayMs = 240;

function appendTextValue(
  value: string,
  onUpdate: (nextValue: string) => void,
) {
  let timeoutMs = 0;

  Array.from(value).forEach((_, characterIndex) => {
    timeoutMs += fillAnimationStepDelayMs;
    window.setTimeout(() => {
      onUpdate(value.slice(0, characterIndex + 1));
    }, timeoutMs);
  });

  return timeoutMs;
}

function animateCredentialsIntoForm(
  credentials: MockCredentials,
  onEmailChange: (nextValue: string) => void,
  onPasswordChange: (nextValue: string) => void,
  onComplete: () => void,
) {
  const emailDurationMs = appendTextValue(credentials.email, onEmailChange);

  window.setTimeout(() => {
    const passwordDurationMs = appendTextValue(
      credentials.password,
      onPasswordChange,
    );

    window.setTimeout(onComplete, passwordDurationMs + loginTransitionDelayMs);
  }, emailDurationMs + fillAnimationStepDelayMs);
}

export function MockAuthLanding() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loadingRole, setLoadingRole] = useState<"admin" | "customer" | null>(
    null,
  );

  function loadMockIdentity(
    identity: MockIdentity,
    destinationPath: "/admin-home" | "/user-home",
    onBeforeNavigate?: () => void,
  ) {
    const credentials = buildMockCredentials(identity);

    setEmail("");
    setPassword("");

    animateCredentialsIntoForm(credentials, setEmail, setPassword, () => {
      onBeforeNavigate?.();
      router.push(destinationPath);
    });
  }

  function handleLoadUser() {
    const customer = getRandomMockCustomer();

    setLoadingRole("customer");
    loadMockIdentity(customer, "/user-home", () => {
      storeSelectedMockCustomer(customer);
    });
  }

  function handleLoadAdmin() {
    setLoadingRole("admin");
    loadMockIdentity(mockAdmin, "/admin-home");
  }

  const isLoading = loadingRole !== null;

  return (
    <main className={styles.page}>
      <div className={styles.content}>
        <header className={styles.header}>
          <h1 className={styles.title}>Refund AI</h1>
          <p className={styles.subtitle}>A customer support agent.</p>
        </header>

        <AppCard>
          <form className={styles.form}>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="email">
                Email
              </label>
              <input
                className={styles.input}
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                value={email}
                readOnly
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="password">
                Password
              </label>
              <input
                className={styles.input}
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                readOnly
              />
            </div>

            <div className={styles.actions}>
              <button
                className={styles.button}
                type="button"
                onClick={handleLoadUser}
                disabled={isLoading}
              >
                {loadingRole === "customer" ? "Loading User" : "Load User"}
              </button>
              <button
                className={`${styles.button} ${styles.buttonSecondary}`}
                type="button"
                onClick={handleLoadAdmin}
                disabled={isLoading}
              >
                {loadingRole === "admin" ? "Loading Admin" : "Load Admin"}
              </button>
            </div>
          </form>
        </AppCard>
      </div>
    </main>
  );
}
