import { fileURLToPath } from "node:url";

/** @type {import('next').NextConfig} */
const config = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  turbopack: { root: fileURLToPath(new URL("../../../", import.meta.url)) },
  env: {
    // The static deployment cannot select the integrated application.
    NEXT_PUBLIC_REFUNDS_AI_DEMO_MODE: "true",
    NEXT_PUBLIC_REFUNDS_AI_STATIC_REFERENCE_DATE: new Date().toISOString(),
  },
};

export default config;
