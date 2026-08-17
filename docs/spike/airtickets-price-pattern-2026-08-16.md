# AirTicketsPrice 資料/API 組織模式研究 → CoolPCTracker 設計提案

> ⚠️ 歷史紀錄：本文為 api/ + 日期制命名改造前的設計提案；文中草擬的 latest_version／versions[]／v{n}.json 於實作時改為 latest_file／files[]／YYYYMMDD[_n].json；2026-08-17 O4 拆檔、再於同日演進為**契約 v2 分類拆檔**（`data/items.json`/`api/latest.json`/`latest_file` 移除，改為 `data/items/{g}.json`/`api/items/{g}.json` 每分類一檔＋`api/index.json` 的 `categories[]`，見 `docs/tech-decisions/tech-decision-資料拆檔方案-2026-08-17.md`）。現行架構見 README「資料/API 組織」，本文僅留作歷程參考。

- 日期：2026-08-16
- 性質：spike（唯讀研究，未改任何程式/資料檔）
- 研究對象：`/fork/YuHaoLiaoSideProject/AirTicketsPrice`
- 目標：把 AirTicketsPrice「資料當成 API、放在同一處、爬蟲產生新 API、index 整理所有 API」的模式映射到 CoolPCTracker

---

## 1. AirTicketsPrice 現況研究

### 1.1 目錄與命名慣例

```
AirTicketsPrice/
├── fetch_prices.py          # 爬蟲（生產資料）
├── build_api.py             # 編譯器：data/*.json → api/ 成品
├── config.py                # 航線/週數/API 設定
├── data/                    # 原始真相（每週一個檔，累積歷史）
│   ├── 20260814.json
│   ├── 20260815.json
│   └── last_notified.json   # 通知 marker（非 list，build_api 自動跳過）
├── api/                     # 衍生 API 成品（每次爬蟲後由 build_api.py 重建）
│   ├── index.json           # ★ 目錄：整理所有 API 的關鍵檔
│   ├── latest.json          # 最新快照（每組合保留最新一筆）
│   └── trips/               # 每趟旅程的價格歷史（畫趨勢圖直接用）
│       └── TPE-NRT/2026-08-15_2026-08-23.json
└── web/                     # 純靜態前端（零建置），runtime 抓 api/
```

關鍵：**`data/` 是「原始真相」（append-only 歷史），`api/` 是「對外 API 成品」（衍生、可重建）**。兩者都 git 版控，但職責分離——crawler 只寫 `data/`，`build_api.py` 只寫 `api/`。

### 1.2 資料真相與 API 成品的分層

| 層 | 目錄 | 寫入者 | 內容 | 消費端 |
|----|------|--------|------|--------|
| 原始 | `data/*.json` | `fetch_prices.py` | 每週原始紀錄（含 `scraped_at`、完整欄位） | 轉存 DB 的人 |
| 成品 | `api/index.json` | `build_api.py` | 目錄/總覽 | **前端第一個 request** |
| 成品 | `api/latest.json` | `build_api.py` | 每 (航線,去程,回程,班號) 最新一筆 | 外部 consumer |
| 成品 | `api/trips/**` | `build_api.py` | 每趟旅程價格歷史（趨勢圖直接抓） | 前端圖表 |

### 1.3 index.json ——「整理所有 API」的關鍵檔（實際範例）

`api/index.json`（節錄，完整欄位見原檔）：

```json
{
  "generated_at": "2026-08-14T22:46:53.000Z",
  "source": "starlux_official_api",
  "description": "星宇航空來回票價歷史（去程週六/回程下週日）",
  "total_records": 478,
  "latest_snapshot_records": 279,
  "routes": ["TPE-CTS", "TPE-FUK", "TPE-KIX", "TPE-NRT"],
  "trip_count": 159,
  "files": [
    {
      "file": "20260814.json",
      "url": "data/20260814.json",
      "records": 200,
      "scraped_at": "2026-08-14T12:21:03.000Z"
    },
    {
      "file": "20260815.json",
      "url": "data/20260815.json",
      "records": 278,
      "scraped_at": "2026-08-14T16:58:04.000Z"
    }
  ],
  "latest_file": "20260815.json",
  "latest": "api/latest.json",
  "trips": [
    "api/trips/TPE-CTS/2026-08-15_2026-08-23.json",
    "api/trips/TPE-NRT/2026-08-15_2026-08-23.json"
  ]
}
```

觀察：
- index 同時是「目錄」（`files[]` 列原始檔、`trips[]` 列所有成品端點）與「指標」（`latest` 指向最新快照、`latest_file` 指向最新原始檔）。
- `routes[]` 是「可查詢維度」的總表（前端航線 tab 的資料來源，但顯示順序仍由前端 CONFIG 控制）。
- 沒有「版本號 int」——AirTicketsPrice 用 `generated_at`（時間戳）+ `latest_file` 檔名當版本訊號，不是 CoolPCTracker 的整數遞增版本。

### 1.4 生產 → 編譯 → 消費串接

workflow（`weekly-crawl.yml`）順序：

```yaml
- run: python fetch_prices.py      # 1. 爬蟲寫 data/YYYYMMDD.json
- run: python build_api.py         # 2. 編譯 data/*.json → api/{index,latest,trips/}
- run: git add data/ api/ && git commit && git push   # 3. 兩層一起入庫
```

`build_api.py` 的核心（對應 CoolPCTracker 未來要做的「整理」）：

```python
def main() -> int:
    records, files_meta = load_all_records()      # 讀全部 data/*.json
    latest = latest_snapshot(records)             # 每 key 保留最新一筆
    trips  = build_trips(records)                 # 分組 → 每趟旅程一條歷史
    index = {
        "generated_at": ...,
        "routes": sorted({r["route_id"] for r in records}),
        "files": files_meta,                      # 來源檔清單
        "latest": "api/latest.json",              # 指標
        "trips": [t["url"] for t in trips],       # 所有成品端點 URL
        ...
    }
    write_json(API_DIR / "index.json", index)
    write_json(API_DIR / "latest.json", latest)
    for t in trips:
        write_json(TRIPS_DIR / f"{route}/{dep}_{ret}.json", t)
```

### 1.5 前端 runtime 發現機制（無 build 注入）

`web/app.js`：

```js
const API_ROOT = new URL('../', document.baseURI);  // 相對 Pages 子路徑，自動解析

async function fetchIndexWithEtag() {
  res = await fetch(new URL('api/index.json', API_ROOT), { cache: 'no-cache', ... });
  json = await res.json();
  // shape 驗證：generated_at / routes / trips 三欄必備
  ...
  return { json, etag: res.headers.get('etag') };
}
```

之後用 `index.trips` 依路徑段篩出該航線的 URL 清單：

```js
const urls = INDEX.trips.filter(t => t.includes('/' + routeId + '/'));
```

**完全 runtime**：沒有 build 期版本注入、沒有 `__DATA_VERSION__`，前端唯一的「真相入口」就是 `api/index.json`。快取失效靠 GitHub Pages 的 ETag + 條件式請求（`If-None-Match`→304），以及 `generated_at` 比對；服務走純靜態 GitHub Pages（另提供 raw / jsDelivr CDN 兩個等價入口）。

---

## 2. AirTicketsPrice 模式提煉（核心模式）

1. **資料真相單一、分兩層**：`data/`（爬蟲 append-only 原始紀錄）是唯一真相；`api/`（index/latest/trips）是衍生成品，隨時可由 `data/` 重建，不存第二份真相。
2. **編譯器分離**：爬蟲（`fetch_prices.py`）只管生產、`build_api.py` 只管把原始資料「編譯成 API」，兩者職責單一、可獨立測試、可單獨重跑。
3. **`api/index.json` 是唯一入口／目錄**：一份檔案同時列出「所有端點」（`files[]`/`trips[]`）、「可查詢維度」（`routes[]`）、「最新指標」（`latest`/`latest_file`）、「時間戳」（`generated_at`）。**這就是「index 整理所有 API」的對應機制**。
4. **版本/新鮮度由 index 承載**：用 `generated_at` + 檔名清單表達「現在有哪些資料、最新是哪份」，消費端不必猜檔名。
5. **生產與消費解耦**：前端只知道 `api/index.json` 這個穩定 URL，不認識爬蟲產出檔名；資料結構演進（新增航線/欄位）只要 index 更新，前端契約不變。
6. **runtime 發現、非 build 注入**：前端啟動時 fetch index → 從 index 拿端點清單 → 再 fetch 各端點；無編譯期版本常數、無手動同步。
7. **純靜態伺服**：`api/` 就是一堆 JSON 檔，靠 GitHub Pages（或 raw/CDN）直接靜態伺服，零後端；Worker 只用於 Web Push，不服務資料。
8. **成品檔名自描述**：`trips/{route}/{dep}_{ret}.json` 路徑即資料維度，前端可從 URL 反解出航線/日期，不依賴檔內欄位。

---

## 3. 映射到 CoolPCTracker

### 3.1 與 AirTicketsPrice 的差異（決定哪些要改寫）

| 面向 | AirTicketsPrice | CoolPCTracker | 映射結果 |
|------|-----------------|---------------|----------|
| 原始資料 | 每週一檔 `data/YYYYMMDD.json` | 單一 `data/items.json`（含 meta+items，每商品自帶 history） | 原始真相留在 `data/`，不變 |
| 版本化 | 檔名日期 + `generated_at` | 整數遞增 `items.v{n}.json` + `meta.json.version` | 保留整數版本，但**把版本快照移進 `api/`** |
| 衍生聚合 | `latest.json` + `trips/**` | 版本快照本身就是「最新完整快照」；無需 per-entity 拆分（history 已在 item 內） | 不需要 `trips/` 聚合；`api/items/v{n}.json` 即成品 |
| 前端 | vanilla JS，runtime fetch | Vue3 + Vite，build 期 `__DATA_VERSION__` 注入 | 改 runtime fetch index，移除注入 |
| 部署 | Pages 直接伺服 repo 根 | Pages 伺服 `web/dist`（build 產物） | build 時把 `api/` 複製進 `dist/`（自動、非手動） |

### 3.2 目標目錄結構（提案）

```
CoolPCTracker/
├── data/                        # 原始真相（crawler 唯一寫入者；git 版控）
│   ├── items.json               # {meta, items}（不變）
│   └── meta.json                # crawled_at/counts/status/version（version 仍由 version_data 遞增）
├── api/                         # ★ 衍生 API 成品（version_data.py 產出；git 版控）
│   ├── index.json               # 目錄：版本清單 + latest 指標 + meta 摘要
│   ├── latest.json              # （可選）穩定端點：最新完整快照
│   └── items/
│       ├── v1.json
│       ├── v2.json
│       └── v3.json              # {crawled_at, items}（沿用現行版本快照形狀）
├── crawler/                     # 不變，仍只寫 data/
├── scripts/
│   └── version_data.py          # 改：diff → 寫 api/items/v{n}.json + 重建 api/index.json
├── web/
│   ├── vite.config.ts           # 改：移除 copyDataPlugin + __DATA_VERSION__；改「serve/copy ../api」
│   ├── src/composables/useItems.ts   # 改：runtime fetch api/index.json → 版本檔
│   ├── e2e/helpers/oracle.ts    # 改：改讀 api/index.json
│   └── public/data/             # 刪（消除手動複製 drift 源）
```

**要點**：
- 保留 `data/` 當「crawler 真相」，不讓 `api/` 取代 `data/`，而是 `api/` 成為**唯一的對外 API 面**（`data/items.json` 仍可保留給轉存/除錯，但前端與外部 consumer 一律走 `api/`）。
- `items.v{n}.json` 從 `data/` 移入 `api/items/v{n}.json`（`git mv` 保留歷史）。

### 3.3 `api/index.json` 設計（CoolPCTracker 版）

```json
{
  "generated_at": "2026-08-16T20:00:00.000Z",
  "source": "https://www.coolpc.com.tw/m/m-list.php",
  "description": "原價屋商品價格追蹤資料 API",
  "latest_version": 3,
  "latest": "api/latest.json",
  "latest_items": "api/items/v3.json",
  "total": 1450,
  "crawled_at": "2026-08-16T06:20:49.650053+00:00",
  "status": "ok",
  "counts": { "CPU": 48, "主機板": 373, "顯示卡": 255 },
  "versions": [
    { "version": 1, "crawled_at": "2026-08-15T...", "total": 1447, "changed": 1447, "url": "api/items/v1.json" },
    { "version": 2, "crawled_at": "2026-08-16T...", "total": 1447, "changed": 1,    "url": "api/items/v2.json" },
    { "version": 3, "crawled_at": "2026-08-16T...", "total": 1450, "changed": 1,    "url": "api/items/v3.json" }
  ]
}
```

對應關係：
- AirTicketsPrice 的 `files[]`（原始檔清單）→ CoolPC 的 `versions[]`（版本快照清單，含 `crawled_at`/`total`/`changed`/`url`）。
- AirTicketsPrice 的 `latest`（指標）→ CoolPC 的 `latest_version` + `latest_items` + `latest`（穩定端點）。
- AirTicketsPrice 的 `routes[]` → CoolPC 可省略（分類維度由前端 `categories.ts` 靜態維護，不隨資料變）；若要動態分類總表，可加 `categories[]`（開放問題）。

### 3.4 資料流（改造後）

```
crawler/main.py ──寫──▶ data/items.json + data/meta.json        （真相，不變）
                                    │
scripts/version_data.py ──讀 data/ 比對上次版本──▶
    ├─ 有異動：寫 api/items/v{n}.json（= {crawled_at, items}）
    │          寫 api/latest.json（= 同內容，穩定端點）
    │          重建 api/index.json（append versions[]、bump latest_version）
    └─ 無異動：不動任何檔（工作流跳過 commit，沿用現有語意）

前端 useItems.ts ──runtime──▶
    1. GET api/index.json  → 取 latest_version（或 latest_items URL）
    2. GET api/items/v{latest_version}.json  → parse → 渲染
    （版本化檔名保留 cache-busting；index 提供 runtime 發現）
```

### 3.5 要改的檔案

| 檔案 | 改動 |
|------|------|
| `scripts/version_data.py` | 從「寫 `data/items.v{n}.json`」改為「寫 `api/items/v{n}.json` + `api/latest.json` + 重建 `api/index.json`」。保留 diff 判異動、`GITHUB_OUTPUT` 輸出 `changed/version`、無異動不寫檔的契約。同步更新 `scripts/tests/test_version_data.py`。 |
| `crawler/store.py` | 幾乎不變（仍寫 `data/items.json` + `data/meta.json`）。僅 docstring/README 把「資料真相」敘述更新為「crawler 真相在 data/，API 成品在 api/」。`meta.json.version` 仍由 version_data 遞增、crawler 沿用。 |
| `web/vite.config.ts` | 移除 `copyDataPlugin`、`__DATA_VERSION__` define、讀 meta.json 取 version。改為單一 plugin：dev 期以 `configureServer` middleware 把 `/api/*` 對應到 `../api`（取代 `web/public/data/` 手動複製）；build 期 `closeBundle` 把 `../api/**` 複製進 `dist/api/`（自動、非手動 drift）。 |
| `web/src/composables/useItems.ts` | `DATA_URL` 改為兩段式：先 `fetch(import.meta.env.BASE_URL + 'api/index.json')` 取 `latest_version`（或 `latest_items`），再 fetch 對應 `api/items/v{n}.json`。`parseItemsFile` 形狀驗證不變。保留 singleton、錯誤分類、重試、過期判定。 |
| `web/e2e/helpers/oracle.ts` | `resolveDataVersion()`/`loadItems()` 改讀 `../api/index.json` 的 `latest_version`（或 `latest_items`），再載 `../api/items/v{n}.json`，與 runtime 行為一致。 |
| `.github/workflows/crawl.yml` | ① Version step 註解/輸出不變；② Commit step `git add data/` → `git add data/ api/`；③ deploy 不變（vite 現在自動帶 `api/`）。 |
| `.gitignore` | `data/*` 例外清單移除 `!data/items.v*.json`（快照已移出 data/）；確認 `api/` 不被 ignore（新目錄，預設已追蹤）；`web/dist/` 維持 ignore（`dist/` pattern 已涵蓋）。 |
| `README.md` / `web/public/data/README.md` | 更新「資料/API 組織」說明（crawler→data/、version_data→api/、前端 runtime fetch index）。 |

### 3.6 要刪的檔案

| 項目 | 理由 |
|------|------|
| `web/public/data/`（整目錄 + `README.md`） | 消除「手動複製」drift 源；dev 改由 vite middleware 服務 `../api`，不再需要 `public/data`。 |
| `web/public/data/items.v0.json`（mock） | mock 資料已存在 `web/src/testing/fixtures.ts`；E2E 用真資料 oracle，離線測試若需要 mock 應改放 `web/e2e/fixtures/`（開放問題）。 |
| `copyDataPlugin`（vite.config.ts 內） | 被「serve/copy `../api`」plugin 取代；不再逐檔選 `items.v{n}.json`。 |
| `__DATA_VERSION__` 注入（vite `define` + `useItems.ts` 常數 + `vite-env.d.ts` 若宣告） | runtime 發現取代 build 注入。 |
| `data/items.v*.json`（`git mv` 至 `api/items/`） | 版本快照歸屬 API 面，避免 `data/` 與 `api/` 各存一份真相。 |

### 3.7 不適合直接套用的部分與替代

1. **AirTicketsPrice 的 `trips/**` 每實體聚合層**：CoolPCTracker 的每商品 history 已內嵌在 item（`history: [[d,p],...]`），版本快照 `api/items/v{n}.json` 本身即「最新完整資料」，無需再造 per-entity 檔案。若未來要「單一商品歷史端點」，可在 build 步驟加 `api/items/{id}.json`，但現階段屬過度設計，**不導入**。
2. **`generated_at` 當唯一版本訊號**：AirTicketsPrice 沒有整數版本。CoolPCTracker 已有 `meta.json.version` + 版本化檔名的 cache-busting 契約（BDD 1→2/5→6/9→10），**保留整數版本**，`generated_at` 只當輔助時間戳。
3. **無 build 的 runtime 部署**：AirTicketsPrice 是零建置 vanilla JS，Pages 直接伺服 repo 根。CoolPCTracker 是 Vue+Vite，Pages 伺服 `web/dist`，所以「runtime 發現」仍須搭配 build 期把 `api/` 複製進 `dist/api/`（自動 copy，非手動 drift）。
4. **raw / jsDelivr CDN 多重入口**：CoolPCTracker 目前只有 Pages；可選用但非必要（開放問題）。
5. **Cloudflare Worker**：AirTicketsPrice 的 Worker 只做 Web Push，與資料 API 無關；CoolPCTracker 用 GitHub Actions + Telegram hook，**不導入**。

---

## 4. 開放問題（需使用者拍板）

1. **meta 歸屬**：`meta.json` 資訊（crawled_at/counts/status/version）要**併入 `api/index.json`**（AirTicketsPrice 模式：index 即總覽），還是**保留獨立 `data/meta.json`** 由 crawler/oracle 讀、index 只放精簡摘要？
2. **版本歷史清單**：`index.json` 的 `versions[]` 要**完整歷史**（AirTicketsPrice `files[]` 模式，可回溯每一版）還是**只留 `latest_version` + 最新一版**（較精簡、index 不會無界成長）？
3. **URL 路徑**：公開 API 路徑是否從 `data/items.v{n}.json` 改成 `api/items/v{n}.json`（GitHub Pages 公開 URL 會變，需確認無外部 consumer 依賴舊路徑）？還是維持 `data/` 路徑、只加 `api/index.json`？
4. **穩定端點 `latest.json`**：是否提供 `api/latest.json`（外部 consumer / Telegram hook 用穩定 URL），還是靠 `index.latest_version` 指到版本檔即可？
5. **前端 fetch 策略**：runtime 拿到 index 後，抓**版本化 `api/items/v{n}.json`**（保留檔名 cache-busting）還是**穩定 `api/latest.json`**（URL 不變，靠 ETag/`generated_at` 比對）？兩者皆可行，前者與現有 cache-busting 契約一致。
6. **舊 `data/items.v*.json` 與 git 歷史**：用 `git mv` 遷移到 `api/items/`（保留歷史），還是直接刪除重建（歷史不重要）？`data/items.v0.json` 等早期快照是否也遷？
7. **dev 資料來源**：dev server 用 vite middleware 服務 `../api`（推薦，零手動複製），還是接受 dev 時需先跑一次 `version_data.py` 產生 `api/`？
8. **mock 資料去處**：`web/public/data/items.v0.json`（離線/無真資料測試用 mock）刪除後，離線測試的 mock 是否改用 `web/src/testing/fixtures.ts` 或 `web/e2e/fixtures/`？
9. **是否順帶導入離線/ETag 快取**：AirTicketsPrice 的 IndexedDB 快取 + ETag 條件式請求是它 offline 功能的基礎；CoolPCTracker 目前無此需求，是否本次只做「index runtime 發現」、離線快取留待後續功能？

---

## 5. 結論摘要

AirTicketsPrice 的核心可移植部分：**「`data/` 真相 + `build_api.py` 編譯 + `api/index.json` 單一入口 + 前端 runtime fetch index」**。映射到 CoolPCTracker 的最小改動是：保留 `data/` 當真相、把版本快照與 index 移入 `api/`、`version_data.py` 兼任「build_api」角色、`useItems.ts` 從 build 注入改 runtime fetch index、刪除 `web/public/data/` 手動複製。純靜態 Pages 的限制用「build 期自動 copy `api/` 進 `dist/`」化解，不引入後端。

*Outcome: OK*
