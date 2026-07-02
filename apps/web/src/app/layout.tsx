import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RefundsAI",
  description: "Policy-governed AI customer support for refund workflows.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
