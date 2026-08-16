// web/vite.config.ts
// 功能 002 §1.7 前端 build 整合合約（003-005 消費）＋ AirTicketsPrice 模式（data/ 真相 + api/ 衍生）
// - base 由 workflow env BASE_PATH 注入（Pages project site 基底路徑），預設 /CoolPCTracker/
// - 單一 inline plugin（無額外 dependency）：
//   dev：configureServer middleware 把 /api/* 對應到 ../api（檔案不存在回 404）；
//   build：closeBundle 把 ../api/** 遞迴複製進 dist/api/（自動、非手動 drift）。
//   前端 runtime fetch(BASE_URL + "api/index.json") → latest_version → api/items/v{n}.json。
// 003：新增 vue plugin、alias @→src、vitest 設定（§2.1 專案初始化）
import { cpSync, existsSync, readFileSync, statSync } from "node:fs";
import { join, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vitest/config";
import vue from "@vitejs/plugin-vue";

const API_DIR = fileURLToPath(new URL("../api", import.meta.url)); // repo 根 /api
const DIST_API_DIR = fileURLToPath(new URL("./dist/api", import.meta.url)); // web/dist/api

/** 單一 plugin：dev 期 serve ../api 為 /api/*；build 期 copy ../api/** → dist/api/ */
const serveCopyApiPlugin: Plugin = {
  name: "coolpc-tracker:serve-copy-api",
  configureServer(server) {
    const base = server.config.base ?? "/";
    server.middlewares.use((req, res, next) => {
      const pathname = (req.url ?? "").split("?")[0];
      let rel = pathname;
      if (base !== "/" && rel.startsWith(base)) rel = rel.slice(base.length);
      rel = rel.replace(/^\/+/, "");
      if (!rel.startsWith("api/")) return next();
      const target = join(API_DIR, rel.slice("api/".length));
      // 防路徑穿越：僅允許落在 API_DIR 內（target === API_DIR 為目錄，走 404）
      if (target !== API_DIR && !target.startsWith(API_DIR + sep)) {
        res.statusCode = 403;
        res.end("Forbidden");
        return;
      }
      if (!existsSync(target) || !statSync(target).isFile()) {
        res.statusCode = 404;
        res.end("Not Found");
        return;
      }
      res.statusCode = 200;
      res.setHeader("Content-Type", "application/json; charset=utf-8");
      res.setHeader("Cache-Control", "no-cache");
      res.end(readFileSync(target));
    });
  },
  closeBundle() {
    if (!existsSync(API_DIR)) {
      console.warn("[vite:api] 找不到 ../api（本地無資料）→ 略過複製");
      return;
    }
    cpSync(API_DIR, DIST_API_DIR, { recursive: true });
    console.log("[vite:api] 已複製 ../api/** → dist/api/");
  },
};

export default defineConfig({
  // Pages project site 掛載於 /{repo}/；workflow 以 BASE_PATH 注入，repo 改名無需改程式碼
  base: process.env.BASE_PATH ?? "/CoolPCTracker/",
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  plugins: [vue(), serveCopyApiPlugin],
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
  },
});
