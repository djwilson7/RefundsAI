import { HomeHeaderCard } from "./home-header-card";
import { getIdentityDisplayName, type MockCustomer } from "./mock-customers";

type CustomerMainScreenProps = Readonly<{
  customer: MockCustomer;
}>;

export function CustomerMainScreen({ customer }: CustomerMainScreenProps) {
  const customerName = getIdentityDisplayName(customer);

  return (
    <HomeHeaderCard
      eyebrow="Welcome"
      heading={customerName}
      summary="Summary Dashboard"
    />
  );
}
