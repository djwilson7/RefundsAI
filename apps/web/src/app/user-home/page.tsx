import { CustomerMainScreen } from "@/components/customer-main-screen";
import { findMockCustomerById, mockCustomers } from "@/components/mock-customers";

type UserHomeProps = Readonly<{
  searchParams: Promise<{
    customerId?: string;
  }>;
}>;

export default async function UserHome({ searchParams }: UserHomeProps) {
  const { customerId } = await searchParams;
  const customer = findMockCustomerById(customerId) ?? mockCustomers[0];

  return <CustomerMainScreen customer={customer} />;
}
