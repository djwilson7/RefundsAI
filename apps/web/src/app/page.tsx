import { MockAuthLanding } from "@/components/mock-auth-landing";
import { ProductLanding } from "@/components/product-landing";
import { isDemoModeEnabled } from "@/lib/demo-mode";
export { isDemoModeEnabled } from "@/lib/demo-mode";

export const dynamic = "force-dynamic";

export default function Home() {
  return isDemoModeEnabled() ? <ProductLanding /> : <MockAuthLanding />;
}
