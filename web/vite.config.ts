// web/vite.config.ts
// 功能 002 §1.7 前端 build 整合合約（003-005 消費）
// - 讀 ../data/meta.json 取得 version → define.__DATA_VERSION__（build 期注入）
// - base 由 workflow env BASE_PATH 注入（Pages project site 基底路徑），預設 /CoolPCTracker/
// - 內建 inline plugin（無額外 dependency）：build 收尾把
//   ../data/items.v{version}.json 與 ../data/meta.json 複製至 dist/data/；
//   來源不存在時略過並印 warning（本地無資料檔仍可 build）
// 003：新增 vue plugin、alias @→src、vitest 設定（§2.1 專案初始化）
import { copyFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vitest/config";
import vue from "@vitejs/plugin-vue";

const WEB_ROOT = fileURLToPath(new URL(".", import.meta.url)); // web/
const DATA_DIR = fileURLToPath(new URL("../data", import.meta.url));
const DIST_DATA_DIR = fileURLToPath(new URL("./dist/data", import.meta.url));

// 讀 ../data/meta.json 取得 cache-busting 版本號（本地無資料檔 → 降級為 0，仍可 build）
let dataVersion = 0;
try {
  const meta = JSON.parse(readFileSync(fileURLToPath(new URL("../data/meta.json", import.meta.url)), "utf-8"));
  dataVersion = typeof meta.version === "number" ? meta.version : 0;
  console.log(`[vite:data] 讀取 ../data/meta.json：version=${dataVersion}`);
} catch {
  console.warn("[vite:data] 找不到 ../data/meta.json（本地無資料檔）→ __DATA_VERSION__ 以 0 注入");
}

/** 複製單一資料檔至 dist/data/；來源不存在 → warning 並略過。 */
function copyToDist(fileName: string): void {
  const src = fileURLToPath(new URL(`../data/${fileName}`, import.meta.url));
  if (!existsSync(src)) {
    console.warn(`[vite:data] 來源不存在，略過複製：../data/${fileName}`);
    return;
  }
  mkdirSync(DIST_DATA_DIR, { recursive: true });
  copyFileSync(src, fileURLToPath(new URL(`./dist/data/${fileName}`, import.meta.url)));
  console.log(`[vite:data] 已複製 ${fileName} → dist/data/`);
}

/** inline plugin：closeBundle 時把資料檔複製進 dist/data/（合約 §1.7；
 *  前端以 items.v{n}.json（版本化檔名自帶快取失效）讀取，不再需要 items.json） */
const copyDataPlugin: Plugin = {
  name: "coolpc-tracker:copy-data-files",
  closeBundle() {
    copyToDist(`items.v${dataVersion}.json`);
    copyToDist("meta.json");
  },
};

export default defineConfig({
  // Pages project site 掛載於 /{repo}/；workflow 以 BASE_PATH 注入，repo 改名無需改程式碼
  base: process.env.BASE_PATH ?? "/CoolPCTracker/",
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  define: {
    // build 期注入 → 前端 fetch(`data/items.v${__DATA_VERSION__}.json`)，快取必然失效（§9.4）
    __DATA_VERSION__: JSON.stringify(dataVersion),
  },
  plugins: [vue(), copyDataPlugin],
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
  },
});
