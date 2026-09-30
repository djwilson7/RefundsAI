"use client";

import Link from "next/link";
import { ArrowRightIcon } from "./icons";
import {
  savePurchaseDetailsSummary,
  type PurchaseDetailsSummary,
} from "@/lib/purchase-details-data";
import styles from "./purchase-history-card.module.css";

type PurchaseHistoryCardProps = Readonly<{
  amount: string;
  href: string;
  purchaseSummary?: PurchaseDetailsSummary;
  purchasedAt: string;
  status: string;
  title: string;
  demo?: boolean;
}>;

export function PurchaseHistoryCard({
  amount,
  href,
  purchaseSummary,
  purchasedAt,
  status,
  title,
  demo = false,
}: PurchaseHistoryCardProps) {
  const purchaseType = purchaseSummary?.purchaseType;
  const cardClassName = [styles.card, purchaseType ? styles[purchaseType] : ""].filter(Boolean).join(" ");
  const content = (
    <>
      <div className={styles.header}>
        <div>
          {purchaseType ? <p className={styles.purchaseType}>{purchaseType}</p> : null}
          <h3 className={styles.title}>{title}</h3>
        </div>
        <p className={styles.amount}>{amount}</p>
      </div>

      <div className={styles.details}>
        <span>{purchasedAt}</span>
        <span className={styles.actionSlot}>
          <span className={styles.status}>{status}</span>
          <span className={styles.arrow}>
            <span>View</span>
            <ArrowRightIcon />
          </span>
        </span>
      </div>
    </>
  );

  return <Link className={cardClassName} href={href} onClick={() => {
    if (!demo && purchaseSummary) savePurchaseDetailsSummary(purchaseSummary);
  }}>{content}</Link>;
}
