// web/src/main.ts
// 功能 002 §1.7 合約的最小消費實作（003 起實作真前端）：
// - 顯示 build 期注入的 __DATA_VERSION__（vite.config.ts define）
// - fetch data/meta.json 顯示 crawled_at；失敗顯示「資料尚未就緒」
/// <reference types="vite/client" />

declare const __DATA_VERSION__: string;

const app = document.querySelector<HTMLDivElement>("#app");
if (app) {
  app.innerHTML = `
    <h1>CoolPC Tracker</h1>
    <p>資料版本：v${__DATA_VERSION__}</p>
    <p id="meta-status">載入中…</p>
  `;
}

fetch(`${import.meta.env.BASE_URL}data/meta.json`)
  .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
  .then((meta: { crawled_at?: string }) => {
    const status = document.querySelector<HTMLParagraphElement>("#meta-status");
    if (status) {
      status.textContent = `最後更新：${meta.crawled_at ?? "未知"}`;
    }
  })
  .catch(() => {
    const status = document.querySelector<HTMLParagraphElement>("#meta-status");
    if (status) {
      status.textContent = "資料尚未就緒";
    }
  });
