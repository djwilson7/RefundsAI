import { CustomerMainScreen } from "@/components/customer-main-screen";
import { findMockCustomerById, mockCustomers } from "@/components/mock-customers";
import { getUserProfile, getUserPurchases } from "@/lib/application-api";
import { buildDemoPurchases } from "@/lib/demo-purchases";
import { isDemoModeEnabled } from "@/lib/demo-mode";
export const dynamic = "force-dynamic";

type UserHomeProps = Readonly<{
  searchParams: Promise<{
    customerId?: string;
    tour?: string;
  }>;
}>;

export default async function UserHome({ searchParams }: UserHomeProps) {
  const { customerId, tour } = await searchParams;
  const fallbackCustomer = findMockCustomerById(customerId) ?? mockCustomers[0];
  if (isDemoModeEnabled() || tour === "client") {
    return <CustomerMainScreen customer={fallbackCustomer} purchases={buildDemoPurchases(fallbackCustomer.id)} demo />;
  }
  const customer = customerId
    ? (await getUserProfile(customerId)) ?? fallbackCustomer
    : fallbackCustomer;
  const purchases = customerId ? (await getUserPurchases(customerId)) ?? [] : [];

  return <CustomerMainScreen customer={customer} purchases={purchases} />;
}
