import { defineConfig, devices } from "@playwright/test";

const apiPort = Number(process.env.E2E_API_PORT ?? 8010);
const webPort = Number(process.env.E2E_WEB_PORT ?? 3001);

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: `http://localhost:${webPort}`,
    trace: "retain-on-failure"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ],
  webServer: [
    {
      command: [
        "rm -f e2e_control_plane.db",
        `DATABASE_URL=sqlite:///./e2e_control_plane.db uv run uvicorn app.main:app --host 127.0.0.1 --port ${apiPort}`
      ].join(" && "),
      cwd: "../api",
      url: `http://localhost:${apiPort}/health/live`,
      reuseExistingServer: false,
      timeout: 30_000
    },
    {
      command: `NEXT_PUBLIC_API_URL=http://localhost:${apiPort} npm run dev -- --port ${webPort}`,
      cwd: ".",
      url: `http://localhost:${webPort}`,
      reuseExistingServer: false,
      timeout: 30_000
    }
  ]
});
