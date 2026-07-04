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
}>;

export function PurchaseHistoryCard({
  amount,
  href,
  purchaseSummary,
  purchasedAt,
  status,
  title,
}: PurchaseHistoryCardProps) {
  return (
    <Link
      className={styles.card}
      href={href}
      onClick={() => {
        if (purchaseSummary) {
          savePurchaseDetailsSummary(purchaseSummary);
        }
      }}
    >
      <div className={styles.header}>
        <h3 className={styles.title}>{title}</h3>
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
    </Link>
  );
}
