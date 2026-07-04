"use client";

import { useRouter } from "next/navigation";
import { AppCard } from "./app-card";
import { IconButton } from "./icon-button";
import { LogoutIcon } from "./icons";
import { clearSelectedMockCustomer } from "./mock-auth-session";
import styles from "./home-header-card.module.css";

type HomeHeaderCardProps = Readonly<{
  eyebrow: string;
  heading: string;
  summary: string;
}>;

export function HomeHeaderCard({
  eyebrow,
  heading,
  summary,
}: HomeHeaderCardProps) {
  const router = useRouter();

  function handleLogout() {
    clearSelectedMockCustomer();
    router.push("/");
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
    </main>
  );
}
