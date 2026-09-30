"use client";

import type { MouseEvent, ReactNode } from "react";

type SmoothScrollLinkProps = {
  children: ReactNode;
  className?: string;
  href: `#${string}`;
};

export function SmoothScrollLink({ children, className, href }: SmoothScrollLinkProps) {
  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    if (
      event.button !== 0 ||
      event.altKey ||
      event.ctrlKey ||
      event.metaKey ||
      event.shiftKey
    ) {
      return;
    }

    const target = document.getElementById(href.slice(1));

    if (!target) {
      return;
    }

    event.preventDefault();
    target.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
      block: "start",
    });
    window.history.pushState(null, "", href);
  }

  return (
    <a className={className} href={href} onClick={handleClick}>
      {children}
    </a>
  );
}
