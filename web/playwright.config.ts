// web/playwright.config.ts — E2E（Playwright）設定（003 篩選功能）
// - webServer 以 vite dev 啟動（dev 模式直接服務 public/data/items.v2.json，即真資料）
// - base 為 /CoolPCTracker/（見 vite.config.ts base），故 URL 需帶 /CoolPCTracker/ 前綴
// - 單 worker 循序執行，避免並行干擾 dev server 與計數斷言
import { defineConfig } from "@playwright/test"

const PORT = 5200
const BASE_URL = `http://localhost:${PORT}/CoolPCTracker/`

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    ["json", { outputFile: "test-results/results.json" }],
  ],
  use: {
    baseURL: BASE_URL,
    browserName: "chromium",
    headless: true,
    viewport: { width: 1280, height: 900 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: `npm run dev -- --port ${PORT} --strictPort`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
})
