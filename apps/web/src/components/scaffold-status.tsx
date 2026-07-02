"use client";

import { motion } from "framer-motion";
import styles from "./scaffold-status.module.css";

const foundationItems = [
  {
    title: "Next.js baseline",
    text: "App Router, TypeScript, production build output, and npm workspace wiring are configured.",
  },
  {
    title: "Frontend validation",
    text: "ESLint and Vitest are available for scaffold checks before product behavior is added.",
  },
  {
    title: "Container runtime",
    text: "The web app has a production Dockerfile and Compose service for local-first development.",
  },
];

export function ScaffoldStatus() {
  return (
    <main className={styles.page}>
      <section className={styles.main} aria-labelledby="scaffold-title">
        <div>
          <p className={styles.eyebrow}>Development foundation</p>
          <h1 id="scaffold-title" className={styles.heading}>
            RefundsAI frontend scaffold is ready.
          </h1>
          <p className={styles.summary}>
            This baseline establishes the web application container, pinned dependencies, styling pipeline, and test harness for the next phase of customer and admin interface work.
          </p>
        </div>

        <div className={styles.grid} aria-label="Frontend foundation status">
          {foundationItems.map((item, index) => (
            <motion.article
              className={styles.item}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              key={item.title}
            >
              <h2 className={styles.itemTitle}>{item.title}</h2>
              <p className={styles.itemText}>{item.text}</p>
            </motion.article>
          ))}
        </div>
      </section>
    </main>
  );
}
