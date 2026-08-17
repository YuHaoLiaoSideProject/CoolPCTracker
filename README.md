# CoolPC Tracker — 原價屋商品價格追蹤

每日自動抓取原價屋手機版 9 個分類頁（約 1,449 商品），以 git 版控的 JSON 累積歷史價格，
GitHub Pages 靜態站 + Telegram 通知。

## 專案現況（2026-08-15）

| 功能 | 狀態 | 說明 |
|------|------|------|
| 001 crawler-data-collection | ✅ 完成 | TDD 開發，155 tests 全綠；fetcher/parser/spec_parser/store/main 6 模組 |
| 002 排程與 Pages 部署 | ✅ 完成 | crawl.yml 每日排程 + workflow_dispatch + cache-busting 版本化 |
| 003-005 前端（Vue 3） | ⏳ Issue #3/#4/#5 | 需 data/*.json 產出後開發 |
| 006 Telegram 價格警報 | ⏳ Issue #7 | |
| 007 健康監控＋警報 | ⏳ Issue #8 | notify hook 簽名已預留 |
| A/B 來源驗證 spike | ⏳ Issue #2 | 手機版 vs 桌面版比對 |

完整 backlog：https://github.com/YuHaoLiaoSideProject/CoolPCTracker/issues

## 文件地圖（每項功能的閱讀鏈）

```
docs/tech-decisions/   ← 技術決策（範圍、資料來源、行動計畫 P0/P1/P2）
docs/interaction-flows/ ← 操作流程（使用者情境、異常處理、驗收清單）
docs/bdds/              ← Gherkin BDD（21 scenario/功能，驗收基準）
docs/development/       ← 開發規格（模組介面、資料結構、測試策略、開發順序）
```

## 如何執行 / 測試

```bash
# 測試（專案已建 .venv）
.venv/bin/python -m pytest crawler/tests -v
.venv/bin/python -m pytest scripts/tests tests -q   # version_data + 基建（gitignore/workflow）

# 手動跑爬蟲（002 完成前之本地驗證）
.venv/bin/python -m crawler.main --data-dir data [--date YYYY-MM-DD]

# 資料異動判定 + 重建 api/（index.json / latest.json / items/YYYYMMDD[_n].json）
.venv/bin/python scripts/version_data.py

# 前端（web/）
cd web && npm ci && npm run dev        # dev server 以 middleware 服務 ../api
cd web && npm run build                 # build 收尾把 ../api/** 複製進 dist/api/
cd web && npm run test:e2e              # Playwright（真資料 oracle 讀 api/index.json）
```

## 如何委派工作給 pi-agent（重要）

**原則：repo 即上下文。** 你只需要給「入口」，agent 會自己讀文件。

| 委派方式 | 範例 | 適合時機 |
|---------|------|---------|
| 最短（建議） | 「處理 issue #8」 | 大部分情況 |
| 指定文件 | 「處理 docs/development/002-scheduler-and-pages-deploy.md」 | 文件比 issue 新 |
| 指定文件＋流程 | 「處理 docs/development/007-crawler-health-monitoring.md，照 001 的 TDD＋sub-session 流程」 | 明確要沿用既有流程 |
| 加偏好 | 「只 review 不要改」「跳過測試計畫」「先做 A 再做 B」 | 有特殊需求 |

Issue 內已含：目標、對應文件路徑、驗收要點 → 指向 issue 即自足。

## 慣用工作流（001 已驗證）

1. **TDD**：每個模組 RED（先寫測試）→ GREEN（最小實作）→ REFACTOR
2. **sub-session 派發**：獨立的模組開發用 sub-session 平行執行；主 session 只做規劃與驗收
3. **loop-review**：完成後多輪審查（Blocking/Major/Minor，fix 模式），至 Blocking=0 停止
4. **完成後**：更新對應 issue（勾選驗收、close）、必要時補 docs

## 資料 / API 組織（AirTicketsPrice 模式：data/ 真相 + api/ 衍生）

```
crawler/main.py ──寫──▶ data/items.json + data/meta.json   （原始真相，git 版控）
                                │
scripts/version_data.py ──讀 data/ 比對上次最新快照──▶
    ├─ 有異動：寫 api/items/{YYYYMMDD[_n]}.json（= {crawled_at, items}）
    │          寫 api/latest.json（穩定端點，同內容）
    │          重建 api/index.json（files[] 完整日期檔清單 + latest_file + merged meta）
    └─ 無異動：不動任何檔

前端 useItems.ts ──runtime──▶
    1. GET api/index.json  → latest_file
    2. GET {latest_file}（api/items/YYYYMMDD[_n].json）→ parse → 渲染
```

- `data/` 是唯一真相（crawler 只寫這裡）；`api/` 是對外 API 面（version_data.py 產出、可重建）。
- `api/index.json` 是前端唯一入口：`files[]` 列完整日期檔歷史、`latest_file` 指向最新檔。
- 快照檔名取自 `crawled_at` 轉 Asia/Taipei（UTC+8）的日期 YYYYMMDD；同日多份依序加 `_1`/`_2`… 後綴。
- 前端 runtime 發現資料檔（不再 build 注入 `__DATA_VERSION__`）；dev 由 vite middleware 服務 `../api`，
  build 時自動把 `../api/**` 複製進 `dist/api/`（非手動 drift）。

## 結構

```
crawler/    Python 爬蟲套件（categories/fetcher/parser/spec_parser/store/main + tests/）
data/       爬蟲輸出（items.json / meta.json，git 版控，首跑由 store 建立）—— 原始真相
api/        衍生 API 成品（version_data.py 產出：index.json / latest.json / items/YYYYMMDD[_n].json）
scripts/    version_data.py（diff → 日期制快照 + 重建 api/index.json）
docs/       全部文件（tech-decisions / interaction-flows / bdds / development）
web/        Vue3 + Vite 前端（runtime fetch api/index.json；build 產出 dist/）
```
