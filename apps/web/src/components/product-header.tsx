"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, type ReactNode } from "react";
import { LogoutIcon, SwapIcon } from "./icons";
import { clearSelectedMockCustomer, storeSelectedMockCustomer } from "./mock-auth-session";
import { findMockCustomerById, mockCustomers } from "./mock-customers";
import styles from "./product-landing.module.css";
import headerStyles from "./product-header.module.css";

type ProductHeaderProps = Readonly<{
  tour?: boolean;
  identityName?: string;
  tourRole?: "client" | "admin";
  customerId?: string;
  helpAction?: ReactNode;
}>;

export function ProductHeader({ tour = false, identityName, tourRole, customerId, helpAction }: ProductHeaderProps) {
  const router = useRouter();
  const swapDialog = useRef<HTMLDialogElement>(null);
  const nextPerspective = tourRole === "admin" ? "Client" : "Admin";

  function swapPerspective() {
    const customer = findMockCustomerById(customerId) ?? mockCustomers[0];
    if (customer) storeSelectedMockCustomer(customer);
    swapDialog.current?.close();
    router.push(tourRole === "admin" ? `/user-home?customerId=${customer.id}&tour=client` : "/admin-home?tour=admin");
  }

  return (
    <nav className={`${styles.nav} ${headerStyles.banner} ${tour ? headerStyles.lightHeader : ""} ${identityName ? headerStyles.identityHeader : ""}`} aria-label="Primary navigation">
      <Link className={styles.brand} href="/" aria-label="RefundsAI home">
        <svg className={styles.lockMark} viewBox="0 0 32 32" fill="none" aria-hidden="true">
          <path d="M8 14.5V11a8 8 0 0 1 16 0v3.5" />
          <path d="M6.5 14.5h19v13h-19z" />
          <path d="M16 19v4" />
        </svg>
        <span className={headerStyles.brandLabel}>RefundsAI</span>
      </Link>
      {identityName ? <h1 className={headerStyles.identity}>{identityName}</h1> : null}
      <div className={headerStyles.actions}>
        {helpAction}
        {tourRole ? (
          <button className={`app-icon-button ${headerStyles.iconButton}`} type="button" onClick={() => swapDialog.current?.showModal()} aria-label={`Switch to ${nextPerspective.toLowerCase()} view`} title={`Switch to ${nextPerspective.toLowerCase()} view`} aria-haspopup="dialog">
            <SwapIcon />
          </button>
        ) : null}
        {tour ? (
          <Link className={`app-icon-button ${headerStyles.iconButton}`} href="/" onClick={clearSelectedMockCustomer} aria-label="Exit" title="Exit tour">
            <LogoutIcon />
          </Link>
        ) : (
          <Link className={styles.tourButton} href="/technical-tour">
            Technical tour <span aria-hidden="true">↗</span>
          </Link>
        )}
      </div>
      {tourRole ? (
        <dialog ref={swapDialog} className={headerStyles.dialog} aria-labelledby="swap-tour-title" aria-describedby="swap-tour-description">
          <h2 id="swap-tour-title">Start the {nextPerspective} tour from the beginning?</h2>
          <p id="swap-tour-description">Your progress through the current tour won’t be saved. Swapping starts the {nextPerspective} tour from the beginning.</p>
          <div className={headerStyles.dialogActions}>
            <button type="button" autoFocus onClick={() => swapDialog.current?.close()}>Continue</button>
            <button type="button" className={headerStyles.confirmSwap} onClick={swapPerspective}>Swap</button>
          </div>
        </dialog>
      ) : null}
    </nav>
  );
}
