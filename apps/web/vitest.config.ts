import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    projects: [
      { extends: true, test: { name: "demo", include: ["src/**/*.demo.test.{ts,tsx}"], env: { REFUNDS_AI_DEMO_MODE: "true" } } },
      { extends: true, test: { name: "integrated", exclude: ["**/node_modules/**", "src/**/*.demo.test.{ts,tsx}"], env: { REFUNDS_AI_DEMO_MODE: "false" } } },
    ],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      thresholds: {
        statements: 90,
        branches: 90,
        functions: 90,
        lines: 90
      }
    }
  },
  resolve: {
    alias: {
      "@": new URL("./src", import.meta.url).pathname
    }
  }
});
