import type { Metadata } from "next";
import { ApplicationHelpLayer } from "@/components/application-help-layer";
import "./globals.css";
import { isDemoModeEnabled } from "@/lib/demo-mode";

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
    // Extensions can inject attributes into the document shell before hydration.
    // Limit suppression to the shell so app components still report mismatches.
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <ApplicationHelpLayer demoMode={isDemoModeEnabled()}>{children}</ApplicationHelpLayer>
      </body>
    </html>
  );
}
