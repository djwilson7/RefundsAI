import type { MockCustomer } from "./mock-customers";

const selectedMockCustomerKey = "refunds-ai:selected-mock-customer";

export function storeSelectedMockCustomer(customer: MockCustomer) {
  window.sessionStorage.setItem(
    selectedMockCustomerKey,
    JSON.stringify(customer),
  );
}

export function clearSelectedMockCustomer() {
  window.sessionStorage.removeItem(selectedMockCustomerKey);
}
