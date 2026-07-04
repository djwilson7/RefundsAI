export type MockIdentity = Readonly<{
  id: string;
  firstName: string;
  lastName: string;
  createdAt: string;
}>;

export type MockCustomer = MockIdentity;

export type MockCredentials = Readonly<{
  email: string;
  password: string;
}>;

const seededCustomerNames = [
  ["20000000-0000-4000-8000-000000000001", "Avery", "Brooks"],
  ["20000000-0000-4000-8000-000000000002", "Maya", "Collins"],
  ["20000000-0000-4000-8000-000000000003", "Jordan", "Reed"],
  ["20000000-0000-4000-8000-000000000004", "Sophia", "Bennett"],
  ["20000000-0000-4000-8000-000000000005", "Marcus", "Hayes"],
  ["20000000-0000-4000-8000-000000000006", "Elena", "Rivera"],
  ["20000000-0000-4000-8000-000000000007", "Noah", "Patel"],
  ["20000000-0000-4000-8000-000000000008", "Lena", "Wright"],
  ["20000000-0000-4000-8000-000000000009", "Caleb", "Morgan"],
  ["20000000-0000-4000-8000-000000000010", "Priya", "Shah"],
  ["20000000-0000-4000-8000-000000000011", "Ethan", "Turner"],
  ["20000000-0000-4000-8000-000000000012", "Grace", "Kim"],
  ["20000000-0000-4000-8000-000000000013", "Lucas", "Carter"],
  ["20000000-0000-4000-8000-000000000014", "Nora", "Evans"],
  ["20000000-0000-4000-8000-000000000015", "Isaac", "Walker"],
] as const;

export const mockCustomers: readonly MockCustomer[] = seededCustomerNames.map(
  ([id, firstName, lastName]) => ({
    id,
    firstName,
    lastName,
    createdAt: "2026-07-03T00:00:00Z",
  }),
);

export const mockAdmin: MockIdentity = {
  id: "20000000-0000-4000-8000-000000000016",
  firstName: "System",
  lastName: "Administrator",
  createdAt: "2026-07-03T00:00:00Z",
};

export function getIdentityDisplayName(identity: MockIdentity) {
  return `${identity.firstName} ${identity.lastName}`;
}

export function getRandomMockCustomer() {
  const randomIndex = Math.floor(Math.random() * mockCustomers.length);

  return mockCustomers[randomIndex];
}

export function findMockCustomerById(customerId: string | undefined) {
  return mockCustomers.find((customer) => customer.id === customerId) ?? null;
}

export function buildMockCredentials(identity: MockIdentity): MockCredentials {
  return {
    email: `${identity.firstName}_${identity.lastName}@example.com`.toLowerCase(),
    password: "12345Password",
  };
}
