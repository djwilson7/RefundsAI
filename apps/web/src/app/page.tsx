import { MockAuthLanding } from "@/components/mock-auth-landing";
import { ProductLanding } from "@/components/product-landing";

export const dynamic = "force-dynamic";

export function isDemoModeEnabled(value = process.env.REFUNDS_AI_DEMO_MODE) {
  return value?.trim().toLowerCase() !== "false";
}

export default function Home() {
  return isDemoModeEnabled() ? <ProductLanding /> : <MockAuthLanding />;
}
