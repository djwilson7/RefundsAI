"use client";

import { useState } from "react";
import { CustomerMainScreen } from "./customer-main-screen";
import { loadSelectedMockCustomer } from "./mock-auth-session";
import { mockCustomers, type MockCustomer } from "./mock-customers";

export function UserHomePage() {
  const [customer] = useState<MockCustomer>(
    () => loadSelectedMockCustomer() ?? mockCustomers[0],
  );

  return <CustomerMainScreen customer={customer} />;
}
