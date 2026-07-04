import { CustomerMainScreen } from "@/components/customer-main-screen";
import { findMockCustomerById, mockCustomers } from "@/components/mock-customers";
import { getUserProfile, getUserPurchases } from "@/lib/application-api";

type UserHomeProps = Readonly<{
  searchParams: Promise<{
    customerId?: string;
  }>;
}>;

export default async function UserHome({ searchParams }: UserHomeProps) {
  const { customerId } = await searchParams;
  const fallbackCustomer = findMockCustomerById(customerId) ?? mockCustomers[0];
  const customer = customerId
    ? (await getUserProfile(customerId)) ?? fallbackCustomer
    : fallbackCustomer;
  const purchases = customerId ? (await getUserPurchases(customerId)) ?? [] : [];

  return <CustomerMainScreen customer={customer} purchases={purchases} />;
}
