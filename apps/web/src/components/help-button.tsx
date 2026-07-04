import type { ButtonHTMLAttributes } from "react";
import { IconButton } from "./icon-button";
import styles from "./help-button.module.css";

type HelpButtonProps = Readonly<
  ButtonHTMLAttributes<HTMLButtonElement> & {
    isOpen: boolean;
    panelId: string;
  }
>;

export function HelpButton({
  isOpen,
  panelId,
  className,
  ...buttonProps
}: HelpButtonProps) {
  const buttonClassName = [styles.button, isOpen ? styles.open : "", className]
    .filter(Boolean)
    .join(" ");

  return (
    <IconButton
      {...buttonProps}
      aria-controls={panelId}
      aria-expanded={isOpen}
      className={buttonClassName}
      icon={isOpen ? <CollapseIcon /> : <ChatIcon />}
      label={isOpen ? "Close help chat" : "Open help chat"}
    />
  );
}

function ChatIcon() {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height="22"
      viewBox="0 0 24 24"
      width="22"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H7l-3 2v-5.5A7.5 7.5 0 1 1 20 11.5Z"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
      <path
        d="M8.5 11.5h.01M12 11.5h.01M15.5 11.5h.01"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.5"
      />
    </svg>
  );
}

function CollapseIcon() {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height="22"
      viewBox="0 0 24 24"
      width="22"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect
        height="14"
        rx="3"
        stroke="currentColor"
        strokeWidth="2"
        width="18"
        x="3"
        y="5"
      />
      <path
        d="M15 5v14"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
    </svg>
  );
}
