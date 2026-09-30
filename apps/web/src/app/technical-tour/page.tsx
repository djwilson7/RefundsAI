import type { Metadata } from "next";
import { TechnicalTour } from "@/components/technical-tour";

export const metadata: Metadata = {
  title: "Technical tour | RefundsAI",
  description: "Explore the client refund experience and the admin audit workspace.",
};

export default function TechnicalTourPage() {
  return <TechnicalTour />;
}
