import type { Metadata } from "next";
import { ApplicationHelpLayer } from "@/components/application-help-layer";
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
      <body>
        <ApplicationHelpLayer>{children}</ApplicationHelpLayer>
      </body>
    </html>
  );
}
