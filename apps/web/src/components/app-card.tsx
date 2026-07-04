import type { ReactNode } from "react";
import styles from "./app-card.module.css";

type AppCardProps = Readonly<{
  children: ReactNode;
  className?: string;
}>;

export function AppCard({ children, className }: AppCardProps) {
  const cardClassName = className ? `${styles.card} ${className}` : styles.card;

  return <section className={cardClassName}>{children}</section>;
}
