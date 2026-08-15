# 開發方案決策文件：原價屋商品價格追蹤

## 📌 決策摘要

| 項目 | 內容 |
|------|------|
| **最終方案** | GitHub 全靜態：GH Actions 每日爬蟲 → JSON → GitHub Pages + Vue 3 靜態站 + Telegram Bot |
| **爬蟲來源** | 📱 原價屋**手機版** `m/m-list.php?G=<索引>`（僅抓所需分類頁） |
| **追蹤範圍** | 9 個分類，約 **1,449 個商品**（CPU/主機板/記憶體/顯示卡/SSD/HDD/套裝/準系統/劈發價組合區/記憶卡） |
| **決策日期** | 2026-08-15 |
| **參與討論** | 專案發起人（透過 tech-assessment-generator 引導） |
| **共識程度** | ✅ 團隊一致通過（單人決策） |

---

## 1. 需求回顧

| 項目 | 決定 |
|------|------|
| **使用者** | 公開網站，任何人可查詢（無需註冊帳號） |
| **追蹤範圍** | 精選 9 個分類（見 §2.3），約 1,449 個商品，非全站 |
| **更新頻率** | 每日一次（GitHub Actions cron 自動觸發） |
| **核心功能** | ① 歷史價格趨勢圖 ② 降價/到價通知 ③ 商品搜尋與篩選 ④ 追蹤清單 ⑤ 同類商品比價 ⑥ 規格解析 |
| **通知管道** | Telegram Bot（無需伺服器，隨每日 run 輪詢） |
| **部署方式** | GitHub Actions 排程爬蟲 → Commit JSON 資料 → GitHub Pages 託管靜態站 |
| **專案定位** | 認真長期維護專案（需考慮資料成長與可維護性） |

---

## 2. 資料來源實測結論（2026-08-15）

### 2.1 原價屋沒有公開 API

實測確認（2026-08-15 實抓）：

- 全站為純 PHP 伺服器渲染 HTML（**Big5/CP950 編碼**），**無任何 JSON/XML 公開 API**
- 探測 `/m/m-search.php`、`/m/m-item.php`、`/m/m-detail.php`、`/api/evaluate`、`?fmt=json` → 全數 404 或照樣回 HTML
- 唯一「互動」端點 `m/my.php` 為 Email 查價清單（購物清單功能），回傳 HTML，非 API
- 商品無獨立明細頁；手機版點商品僅將名稱加入清單表單

→ **爬蟲為唯一途徑**，採用手機版分類頁作為來源。

### 2.2 手機版 vs 桌面版（爬蟲來源比較）

| 比較 | 桌面版 evaluate.php | 📱 手機版 m-list.php（**採用**） |
|------|:---:|:---:|
| 請求次數 | 1 次（1MB 單頁） | 31 次（每頁 ~46KB） |
| 商品數 | 7,319 個 OPTION（含加購/贈品垃圾項） | **6,626 個乾淨商品** |
| 分類結構 | 570 個細分類需自行映射至大分類 | **31 個主分類現成**（CPU/主機板/記憶體/顯示卡/螢幕/機殼/電源…） |
| HTML 結構 | 巨型 `<select>` + OPTGROUP/OPTION | 乾淨 table：`<th>`=子分類標題、`<td>`=商品列 |
| 標記 | `◆`=有貨、`★`=熱賣、`↓任搭/酷幣↓` | `Hot！`=熱賣、`任搭↓N`=促銷、`↘`=降價顯示、`尾盤`=清倉 |
| 優點 | 單次請求全站 | 分類現成、結構乾淨、重抓成本低 |
| 缺點 | 需自建分類映射、含垃圾項 | 31 次請求、標記語意需重新確認 |

**採用理由**：分類結構現成（省去 570→20 映射工程）、商品資料乾淨、失敗重抓成本低。

### 2.3 最終追蹤範圍（2026-08-15 討論確認）

| 分類 | 手機版頁 | 商品數 | 備註 |
|------|:---:|:---:|------|
| CPU | G=4 | 48 | |
| 主機板 | G=5 | 373 | |
| 記憶體 | G=6 | 216 | |
| 顯示卡 | G=12 | 255 | |
| SSD | G=7 | 171 | M.2 / SATA 固態硬碟 |
| HDD | G=8 | 89 | 傳統內接硬碟 |
| 套裝/準系統 | G=1 | 157 | 套裝主機 / AIO / 迷你準系統 |
| 劈發價組合區 | G=3 | 86 | 限時限量優惠組合 |
| 記憶卡 | G=9（4 個子分類） | 54 | 僅 Micro SD / SD / CFexpress / MicroSDXC Express 子分類，排除隨身碟/外接碟 |
| **合計** | 9 頁 | **≈ 1,449** | 全站 6,626 的 22% |

**範圍策略**：
- G=9 為「外接硬碟/隨身碟/記憶卡」混合頁，以**子分類名稱含「記憶卡」**精準篩選
- 追蹤範圍縮小 → 資料量小、搜尋快、每商品歷史更完整（趨勢圖品質更高）

---

## 3. 最終方案

### 3.1 技術棧

| 層級 | 技術 | 版本 | 備註 |
|------|------|------|------|
| 爬蟲 | Python | 3.12 | httpx + selectolax（或 BeautifulSoup4） |
| 排程 | GitHub Actions | - | cron `0 6 * * *`（UTC 06:00 = 台北 14:00，錯開原價屋上午更新） |
| 資料 | JSON（git 版控） | - | delta 歷史，僅異動時 append |
| 前端 | Vue 3 + Vite + TypeScript | Vue 3.5 / Vite 6 | Composition API + Pinia（視需要） |
| 圖表 | ECharts | 5.x | on-demand import，trend chart + markLine 目標價 |
| 部署 | GitHub Pages | - | `actions/deploy-pages` 或 peaceiris/gh-pages |
| 通知 | Telegram Bot API | - | 每日 run 內輪詢 getUpdates，無 webhook 需求 |
| 測試 | pytest（爬蟲）+ Vitest（前端） | - | parser 用 fixture HTML 測試 |

### 3.2 架構概覽

```
┌─────────────────────────────────────────────────────────┐
│  GitHub Actions（每日 06:00 UTC，cron）                  │
│                                                         │
│  ① fetcher:  抓取 m-list.php?G=1,3,4,5,6,7,8,9,12       │
│               （Big5, UA, retry）                       │
│  ② parser:   9 個分類頁 table → 1,449 商品 + 主/子分類    │
│               （G=9 僅取「記憶卡」子分類）               │
│  ③ spec_parser: 商品名 → 結構化規格（CPU/GPU/RAM/SSD/PSU…）│
│  ④ store:    與 data/items.json diff → append 歷史       │
│  ⑤ telegram:  輪詢指令 + 比對目標價 → 寄降價通知          │
│  ⑥ build:    前端 Vite build → 部署 GitHub Pages        │
└─────────────────────────────────────────────────────────┘
                        │  commit JSON
                        ▼
      ┌─────────────────────────────────────┐
      │  GitHub Pages 靜態站                  │
      │  Vue 3 SPA 讀取 data/*.json           │
      │  • 搜尋/篩選 • 趨勢圖 • 比價 • 追蹤清單 │
      └─────────────────────────────────────┘
```

### 3.3 專案結構

```
coolpc-tracker/
├── .github/workflows/
│   └── crawl.yml              # 每日爬蟲 + Telegram + 部署 Pages
├── crawler/
│   ├── pyproject.toml
│   ├── main.py                # 總排程（fetch→parse→store→telegram）
│   ├── fetcher.py             # 抓 9 個分類頁 + cp950 解碼 + retry + UA
│   ├── categories.py          # 分類清單（G 索引、名稱、記憶卡子分類過濾）
│   ├── parser.py              # HTML table → RawItem（含 disabled/促銷過濾）
│   ├── spec_parser.py         # 商品名 → 結構化 spec（CPU/GPU/…）
│   ├── store.py               # delta diff、歷史 append、JSON 輸出
│   └── telegram_bot.py        # getUpdates 輪詢、/watch、降價通知
├── data/                      # git 版控的資料（來源真相）
│   ├── items.json             # 全部商品 + compact 歷史
│   ├── meta.json              # 最後爬取時間、計數、健康指標
│   └── telegram.json          # bot offset + 使用者追蹤清單
├── web/                       # Vue 3 + Vite + TS
│   ├── src/ (views: 首頁/分類/商品詳情/比價/追蹤/說明)
│   └── vite.config.ts         # base 依 repo name
└── docs/                      # 本文件與後續技術文件
```

### 3.4 資料模型（草稿）

```jsonc
// data/items.json
{
  "meta": { "crawled_at": "2026-08-15T06:00:00Z", "source": "https://www.coolpc.com.tw/m/m-list.php" },
  "items": [
    {
      "id": "3f9a1c2b8e4d5f6a",                  // sha256(主分類 + 正規化名稱) 取前 16 位 hex，跨日穩定
      "category": "CPU",
      "name": "Intel i5-13600K【14核/20緒】3.5GHz(↑5.1G)/20M/UHD770/125W【代理盒裝】",
      "spec": { "brand": "Intel", "model": "i5-13600K", "cores": 14, "threads": 20,
                "base_ghz": 3.5, "turbo_ghz": 5.1, "tdp_w": 125, "socket": "LGA1700" },
      "flags": { "hot": true, "promo": "任搭190" },
      "status": "in_stock",                     // in_stock / gone（以是否出現在當日清單判定）
      "first_seen": "2026-08-15",
      "last_seen": "2026-08-16",
      "history": [ ["2026-08-15", 9990] ]            // compact [d,p] 陣列；僅異動時 append
    }
  ]
}
```

---

## 4. 行動計畫

### 4.1 初期任務

| 優先級 | 任務 | 預估 | 依賴 |
|--------|------|------|------|
| P0 | repo 初始化（gitignore、README、目錄） | 0.5d | - |
| P0 | fetcher：抓 31 分類頁 + cp950 解碼 + retry + UA | 0.5d | - |
| P0 | parser：table 解析 + 主/子分類 + 過濾規則 + fixture 測試 | 1d | - |
| P0 | **A/B 驗證**：手機版 vs 桌面版各抓一次比對，確認無漏品 | 0.5d | P0 parser |
| P0 | store：delta diff + 歷史 append + items.json 輸出 | 1d | - |
| P0 | crawl.yml：每日 cron + commit 資料 + Pages 部署 | 0.5d | 上述 |
| P1 | spec_parser：CPU/GPU/RAM/SSD/HDD/主機板深度解析 + 記憶卡/套裝機輕量解析 | 2d | - |
| P1 | 前端骨架：Vue + Vite + 資料載入 + 分類頁 + 商品列表 | 2d | - |
| P1 | 搜尋與篩選（全文 + spec 篩選，如 VRAM≥12G） | 1d | - |
| P1 | 商品詳情 + ECharts 歷史趨勢圖 | 1.5d | - |
| P1 | 追蹤清單（localStorage）+ 比價（多選比較表） | 1.5d | - |
| P2 | Telegram bot：輪詢 /watch、目標價、降價通知 | 2d | store |
| P2 | 健康監控：解析異常（商品數驟降 >20%）→ Telegram 管理員警報，不覆寫資料 | 0.5d | - |
| P2 | 資料成長檢核與 minify（compact arrays） | 0.5d | - |

### 4.2 有待驗證的項目（Spike）

- **A/B 來源比對**：手機版 vs 桌面版商品集合差異（第一天兩邊各抓一次）
- **手機版標記語意**：`Hot！`/`任搭↓N`/`↘`/`尾盤` 的準確意義與穩定度（觀察數日）
- **selectolax vs BeautifulSoup4**：Big5 HTML 解析速度與健壯性
- **GitHub Pages JSON 快取**：資料更新後瀏覽器/Pages 快取行為（可能需要 cache-busting 檔名 `items.v{n}.json`）

---

## 5. 風險登錄

| 風險 | 可能性 | 影響 | 緩解措施 |
|------|--------|------|---------|
| 原價屋改版 HTML 結構 → parser 失效 | 中 | 高 | 版本化 parser + 商品數驟降偵測 → 管理員 Telegram 警報，保留舊資料不覆寫 |
| 商品無穩定 ID，名稱改動造成重複/失蹤 | 中 | 中 | 正規化名稱產生 ID；以「名稱相似度 + 價格連續性」做 merge 策略 |
| Big5 編碼/特殊字元解析失敗 | 低 | 中 | cp950 + errors='replace'；fixture 涵蓋特殊字元 |
| repo 體積隨歷史成長 | 中 | 低 | delta 歷史 + compact 陣列；年度體積檢核 |
| GH Actions 排程延遲/跳過 | 低 | 低 | workflow_dispatch 手動補爬；資料帶 crawled_at 顯示新鮮度 |
| Telegram Bot API 限制（rate limit、token 失效） | 低 | 低 | 每日僅少量訊息；token 存 secret |
| 流量暴增導致 Pages 頻寬超限 | 低 | 中 | Pages 免費額度 100GB/月，超限僅暫停服務，成本可控 |

---

## 📝 決策後續

- 本文件已存至 `docs/tech-decisions/tech-decision-原價屋商品價格追蹤-2026-08-15.md`，納入版本控制
- 建議 1 個月後回顧：parser 穩定性、資料成長量、使用者回饋
- 若原價屋大改版或需求升級（如即時通知、帳號），可重新啟動討論
