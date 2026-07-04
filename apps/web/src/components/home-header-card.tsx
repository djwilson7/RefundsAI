"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { AppCard } from "./app-card";
import { IconButton } from "./icon-button";
import { LogoutIcon } from "./icons";
import { clearSelectedMockCustomer } from "./mock-auth-session";
import styles from "./home-header-card.module.css";

type HomeHeaderCardProps = Readonly<{
  eyebrow: string;
  heading: string;
  summary: string;
  children?: ReactNode;
}>;

export function HomeHeaderCard({
  children,
  eyebrow,
  heading,
  summary,
}: HomeHeaderCardProps) {
  const router = useRouter();

  function handleLogout() {
    clearSelectedMockCustomer();
    router.replace("/");
  }

  return (
    <main className={styles.page}>
      <AppCard className={styles.content}>
        <div className={styles.header}>
          <p className={styles.eyebrow}>{eyebrow}</p>
          <IconButton
            icon={<LogoutIcon />}
            label="Log out"
            onClick={handleLogout}
            variant="danger"
          />
        </div>
        <h1 className={styles.heading}>{heading}</h1>
        <p className={styles.summary}>{summary}</p>
      </AppCard>
      {children ? <div className={styles.body}>{children}</div> : null}
    </main>
  );
}
