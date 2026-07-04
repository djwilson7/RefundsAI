import type { ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./icon-button.module.css";

type IconButtonVariant = "default" | "danger";

type IconButtonProps = Readonly<
  ButtonHTMLAttributes<HTMLButtonElement> & {
    label: string;
    icon: ReactNode;
    variant?: IconButtonVariant;
  }
>;

export function IconButton({
  icon,
  label,
  type = "button",
  variant = "default",
  className,
  ...buttonProps
}: IconButtonProps) {
  const variantClassName = variant === "danger" ? styles.danger : "";
  const buttonClassName = [styles.button, variantClassName, className]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      {...buttonProps}
      aria-label={label}
      className={buttonClassName}
      type={type}
    >
      {icon}
    </button>
  );
}
