import type { MockCustomer } from "./mock-customers";

const selectedMockCustomerKey = "refunds-ai:selected-mock-customer";

export function storeSelectedMockCustomer(customer: MockCustomer) {
  window.sessionStorage.setItem(
    selectedMockCustomerKey,
    JSON.stringify(customer),
  );
}

export function loadSelectedMockCustomer() {
  if (typeof window === "undefined") {
    return null;
  }

  const storedCustomer = window.sessionStorage.getItem(selectedMockCustomerKey);

  if (!storedCustomer) {
    return null;
  }

  return JSON.parse(storedCustomer) as MockCustomer;
}
