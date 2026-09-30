import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  env: {
    NEXT_PUBLIC_REFUNDS_AI_DEMO_MODE: process.env.REFUNDS_AI_DEMO_MODE ?? "true",
  },
  async headers() {
    if (process.env.REFUNDS_AI_DEMO_MODE?.trim().toLowerCase() === "false") return [];
    return [{ source: "/:path*", headers: [{
      key: "Content-Security-Policy",
      value: `default-src 'self'; script-src 'self' 'unsafe-inline'${process.env.NODE_ENV === "production" ? "" : " 'unsafe-eval'"}; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data: blob:; font-src 'self' data:; media-src 'self' blob:; frame-src 'none'; form-action 'self'; object-src 'none'; base-uri 'self'`,
    }] }];
  },
};

export default nextConfig;
