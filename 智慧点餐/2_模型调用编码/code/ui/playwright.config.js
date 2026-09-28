import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 90000,
  workers: 1,
  use: { viewport: { width: 1440, height: 1100 }, trace: "retain-on-failure" },
  webServer: [
    {
      command: "python ../tests/serve_e2e.py",
      url: "http://127.0.0.1:8001/health",
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --port 3001",
      url: "http://127.0.0.1:3001",
      reuseExistingServer: false,
      env: { AIMENU_API_TARGET: "http://127.0.0.1:8001" },
    },
  ],
});
