"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function NotFound() {
  useEffect(() => { window.location.replace("/"); }, []);
  return <Link href="/">Return to RefundsAI</Link>;
}
