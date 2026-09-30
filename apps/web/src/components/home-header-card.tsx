"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { AppCard } from "./app-card";
import { IconButton } from "./icon-button";
import { LogoutIcon } from "./icons";
import { clearSelectedMockCustomer } from "./mock-auth-session";
import { ProductHeader } from "./product-header";
import shellStyles from "./tour-shell.module.css";
import styles from "./home-header-card.module.css";

type HomeHeaderCardProps = Readonly<{
  eyebrow: string;
  heading: string;
  summary: string;
  children?: ReactNode;
  productBanner?: boolean;
  customerId?: string;
  helpAction?: ReactNode;
  tourRole?: "client" | "admin";
}>;

export function HomeHeaderCard({
  children,
  eyebrow,
  heading,
  summary,
  productBanner = false,
  customerId,
  helpAction,
  tourRole = "client",
}: HomeHeaderCardProps) {
  const router = useRouter();

  function handleLogout() {
    clearSelectedMockCustomer();
    router.replace("/");
  }

  return (
    <div className={productBanner ? shellStyles.page : undefined}>
      {productBanner ? <ProductHeader tour identityName={heading} tourRole={tourRole} customerId={customerId} helpAction={helpAction} /> : null}
      <main className={`${styles.page} ${productBanner ? styles.tourPage : ""}`}>
        {!productBanner ? <AppCard className={styles.content}>
          <div className={styles.header}>
            <p className={styles.eyebrow}>{eyebrow}</p>
            {!productBanner ? (
              <IconButton
                icon={<LogoutIcon />}
                label="Log out"
                onClick={handleLogout}
                variant="danger"
              />
            ) : null}
          </div>
          {!productBanner ? <h1 className={styles.heading}>{heading}</h1> : null}
          <p className={styles.summary}>{summary}</p>
        </AppCard> : null}
        {children ? <div className={styles.body}>{children}</div> : null}
      </main>
    </div>
  );
}
