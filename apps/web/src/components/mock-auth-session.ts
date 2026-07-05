import type { MockCustomer } from "./mock-customers";

const selectedMockCustomerKey = "refunds-ai:selected-mock-customer";

export function storeSelectedMockCustomer(customer: MockCustomer) {
  window.sessionStorage.setItem(
    selectedMockCustomerKey,
    JSON.stringify(customer),
  );
}

export function loadSelectedMockCustomerId() {
  if (typeof window === "undefined") {
    return null;
  }

  const storedCustomer = window.sessionStorage.getItem(selectedMockCustomerKey);

  if (!storedCustomer) {
    return null;
  }

  try {
    const parsed = JSON.parse(storedCustomer) as Partial<MockCustomer>;

    return typeof parsed.id === "string" ? parsed.id : null;
  } catch {
    return null;
  }
}

export function clearSelectedMockCustomer() {
  window.sessionStorage.removeItem(selectedMockCustomerKey);
}
