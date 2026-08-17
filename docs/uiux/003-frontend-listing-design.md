# UI/UX 設計文件 — 003 前端列表與搜尋（frontend-listing-search）

> 文件類型：完整規格（綠地專案，無既有 UI，不做 BEFORE/AFTER 比較稿）
> 對應開發規格：`docs/development/003-frontend-listing-search.md`（§7 CSS token 為設計依據）
> 對應 BDD：`docs/bdds/003-frontend-listing-search.feature`（24 Scenario）
> 對應操作流程：`docs/interaction-flows/003-frontend-listing-search.md`
> 互動 mockup：`docs/uiux/003-frontend-listing-design.html`
> 共用 token：與 004 平行子任務共用，**不可更動**

---

## 1. 現況審計（Greenfield 如實記錄）

先讀 `web/` 原始碼後下結論：**web/ 為綠地**，無既有 UI 可審計、無需比對、無回歸風險。審計表記錄現況事實與設計依據來源。

| # | 現況事實／問題 | 嚴重度 | 位置 | 說明 |
|---|--------------|--------|------|------|
| 1 | 無任何 Vue 元件、無 CSS 樣式檔、無 router | P1（設計依據） | `web/src/` | 僅 `src/main.ts`（002 最小消費實作：`innerHTML` 渲染標題＋`meta-status`）。003 起全數元件化 |
| 2 | 002 最小消費實作將被 003 取代（`innerHTML` → Vue 元件） | P3 | `web/src/main.ts` | 003 改為 `createApp` + `createWebHashHistory` router + 元件掛載 |
| 3 | 無設計 token、無 RWD 斷點樣式 | P1 | `web/`（全） | 本文件 §4 以開發規格 §7.1 token 為唯一來源落地 |
| 4 | 資料合約已具備：`vite.config.ts` 單一 plugin 於 dev 將 `../api/**` 服務為 `/api/*`、build 自動 copy 進 `dist/api/`；前端 runtime 讀 `api/index.json` → `latest_file` → `api/items/YYYYMMDD[_n].json` | P2（沿用） | `web/vite.config.ts` | 003 載入層（`useItems`）直接消費，無需改動 build 合約 |
| 5 | 無任何狀態處理（loading／error／empty）之既有實作 | P1 | `web/src/` | 本文件 §5 定義八態狀態矩陣，實作需全數覆蓋（BDD @error-handling @edge-case） |
| 6 | 無無障礙基礎（focus ring／aria／對比） | P2 | `web/`（全） | 本文件 §7 定義 WCAG 規格供實作遵循 |

> 設計依據優先序：開發規格 §7（CSS token）＞ BDD（24 Scenario 語意）＞ Interaction Flow（操作步驟）。共用 token 值以本文件 §4 為準，004 不得更動。

---

## 2. 設計原則

1. **單一事實來源、資料驅動 UI** — 分類清單只來自 `data/categories.ts` 常數（與爬蟲 `categories.py` 同步）；商品欄位只來自 `types/item.ts` 契約。側欄、篩選、卡片永不硬編碼資料，BDD「側欄僅 9 大分類」天然滿足。
2. **漸進式揭露、錯誤不佔位** — 載入／錯誤只影響列表區域：側欄、搜尋框、篩選面板**照常渲染**（BDD：載入失敗頁面不白屏）。過期橫幅是資訊提示，不是錯誤，資料仍正常顯示。
3. **語意化圖示與色彩** — 圖示一律 inline SVG（`aria-hidden`）；漲跌同時以「顏色＋文字」（漲/跌/持平/—）傳達，不單靠顏色（WCAG 1.4.1）。
4. **觸控與鍵盤優先** — 行動端觸控目標 44px（WCAG 2.5.5）；`focus-visible` 3px 光圈；卡片 `tabindex=0` 且 Enter/Space 可觸發（004 前即具鍵盤可操作性）。
5. **狀態完整覆蓋，不畫 happy path** — 載入 skeleton、錯誤＋重試、空結果三分流（搜尋／篩選／空分類）、資料缺漏降級（缺昨日價「—」、sparkline 資料不足「—」）皆為一等公民狀態。

---

## 3. Design Token 表

共用 token（與 004 一致，**不可更動**）。深色主題為本文件自訂對應值，兩主題皆可讀。

| Token | Light | Dark | 用途 |
|-------|-------|------|------|
| `--brand` | `#1f6feb` | `#4c8dff` | 主品牌色：側欄 active、卡片 hover border、sparkline、重試按鈕 |
| `--brand-soft` | `#e8f0fe` | `#1d2f4d` | 品牌淡底：active 分類、條件 chip、anatomy tag |
| `--price-up` | `#e02424` | `#f87171` | 漲（紅） |
| `--price-down` | `#18933f` | `#4ade80` | 跌（綠） |
| `--price-flat` | `#6b7280` | `#9ca3af` | 持平（灰） |
| `--bg` | `#f7f8fa` | `#0f141a` | 頁面背景 |
| `--surface` | `#ffffff` | `#161c24` | 卡片／輸入框／面板表面 |
| `--border` | `#e5e7eb` | `#2a3340` | 邊框 |
| `--text` | `#1f2937` | `#e5e7eb` | 主文字 |
| `--text-dim` | `#6b7280` | `#8b95a3` | 次要文字（計數、hint、空狀態） |
| `--warn-bg` | `#fff7e6` | `#2b230f` | 過期橫幅背景 |
| `--warn-border` | `#f5c518` | `#f5c518` | 過期橫幅邊框 |
| `--warn-text` | `#8a6d00` | `#f2d57a` | 過期橫幅文字 |
| `--radius` | `10px` | `10px` | 卡片／面板圓角 |
| `--radius-sm` | `6px` | `6px` | 按鈕／輸入／分類項圓角 |
| `--shadow` | `0 1px 3px rgba(0,0,0,.08)` | `0 1px 3px rgba(0,0,0,.5)` | 卡片陰影 |
| `--h` | `36px` | `36px` | 桌面控制高度（搜尋、按鈕、分類項） |
| `--h-mobile` | `44px` | `44px` | 行動控制高度（WCAG 2.5.5） |
| `--fs` | `0.875rem` | `0.875rem` | 基礎字級（輸入／按鈕） |

衍生語意色（light / dark）：

| 語意 | Light | Dark | 用途 |
|------|-------|------|------|
| accent | `#1a73e8` | `#8ab4f8` | 焦點、連結、active 強調 |
| success | `#188038` | `#81c995` | 成功 |
| danger | `#c5221f` | `#f28b82` | 錯誤、表單錯誤訊息 |
| warning | `#e37400` | `#fdd663` | 警告 |

其他規範：

| 項目 | 值 |
|------|-----|
| 字級階層 | 卡片名稱 `.95rem/600`、目前價 `1.15rem/700`、漲跌 `.85rem/600`、spec chip `.72rem`、計數 meta `.78rem` |
| 間距 | 卡片內 12/14px、grid gap 12px、群組間 16px、控制群組內 8px |
| 動畫 | transition `0.2s ease`；內容淡入 `150ms`；skeleton shimmer `1.2s infinite`；尊重 `prefers-reduced-motion` |
| Focus ring | `:focus-visible` 3px `rgba(26,115,232,.14)` 光圈（accent） |
| 字體 | `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans TC", "PingFang TC", "Microsoft JhengHei"` |
| Mono | `ui-monospace, SFMono-Regular, Menlo, Consolas` |
| 圖示 | inline SVG（`aria-hidden`），不使用 emoji 當圖示 |
| 語言 | 中文繁體（zh-Hant） |

---

## 4. 狀態矩陣

覆蓋 8 態：idle / hover / focus / active / disabled / loading / error / 空結果。

| 狀態 | 視覺 | 互動 |
|------|------|------|
| **idle** | 卡片：`surface` 底、`border` 邊框、`shadow` 陰影、文字 `text`；分類項透明底 | 可點擊／可輸入；卡片 `cursor: pointer`（004 入口預告） |
| **hover** | 卡片 `border-color: brand` + `0 2px 8px rgba(31,111,235,.15)`；分類項淡 `brand-soft` 底；按鈕 `surface-2` 底 | 提示可操作；hover 不改變佈局（無位移） |
| **focus** | `:focus-visible` 3px accent 光圈（搜尋、按鈕、chips、卡片 `tabindex=0`）；不透明度不低於 3:1 | 鍵盤 Enter/Space 可觸發卡片（004）、按鈕、chip 移除 |
| **active** | 側欄分類 `brand-soft` 底 + `brand` 字 + 700 weight + brand 邊框；segmented demo 按鈕白底＋accent 字 | `aria-pressed="true"`；URL 同步 `?category=<key>`（mockup 更新 browser-bar URL） |
| **disabled** | `opacity: .5` + `cursor: not-allowed` | 無法點擊（例：無任何條件時「清除全部條件」按鈕 disabled） |
| **loading** | 列表區 skeleton 卡片（灰階 shimmer 1.2s）；側欄／搜尋框／篩選面板照常渲染 | `aria-busy="true"`；不白屏（BDD smoke） |
| **error** | 列表區 `ErrorState`：SVG 圖示 +「資料載入失敗／資料格式錯誤」+ 重試按鈕（brand 底白字） | 點「重試」→ loading → 重新載入；錯誤只影響列表區，側欄與搜尋仍可用 |
| **空結果** | `EmptyState` 三分流：搜尋（「沒有符合『xx』的商品」）、篩選（列出條件＋「沒有符合條件的商品」）、空分類（「此分類目前沒有商品」，純說明不報錯） | 搜尋/篩選空 → 提供清除按鈕；空分類 → 「查看全部商品」回全部；皆不觸發重試 |

空狀態分流優先序（§6.2）：`keyword` 有值 → search；否則 `conditions` 有值 → filter；否則 → category。

---

## 5. RWD 斷點行為表

> 實作斷點以開發規格 §7.6 為準（`max-width:1023px`／`max-width:639px`）；本表以 1024／768／767 三帶描述行為，兩者對應一致（639–767 之間 `cat-grid` 的 `minmax(300px,1fr)` auto-fill 已自然單欄）。

| 行為 | ≥1024（桌面） | 768–1023（平板） | ≤767（手機） |
|------|--------------|------------------|--------------|
| 整體佈局 | `.listing` grid `240px 1fr`、`max-width:1200px`、padding 16px、gap 20px | 單欄 `1fr`、側欄 `position: static` | 單欄、padding 10px、gap 12px |
| 分類側欄 | 左側 240px sticky（`top:72px`），垂直列表，項目高 36px | 收合為頂部水平捲動 chips（`overflow-x:auto`），項目高 36px | 水平捲動 chips，項目高 **44px**（`--h-mobile`） |
| 商品卡片 | `cat-grid` auto-fill `minmax(300px,1fr)` 多欄（1200px 寬約 3 欄） | 維持多欄（content 寬仍 ≥300px×2 時） | 單欄（639 以下）；`pc-price` `flex-wrap` 價格可換行堆疊 |
| 控制元件 | 36px（`--h`）：搜尋框、套用、重試、清除按鈕 | 36px | **44px**（`--h-mobile`，WCAG 2.5.5） |
| 搜尋框 | 彈性寬度，`max-width:400px` | 彈性寬度 | 全寬（`max-width:none`） |
| 過期橫幅 | 頂部全寬 `warn` 色系橫幅 | 同左 | 同左（文字可換行） |

---

## 6. 無障礙清單（WCAG）

| 準則 | 要求 | 對應設計 |
|------|------|----------|
| **1.4.1** 不以顏色單獨傳達 | 漲跌資訊不得只靠紅／綠 | 每筆 delta 同時顯示「漲 500／跌 300／持平／—」文字；`deltaClass` 只做強化 |
| **2.5.5** 目標尺寸 | 觸控目標 ≥ 40×40px | 行動端控制一律 44px（`--h-mobile`）；chip 移除鈕 20px 但含在 44px chip 觸控區內（補 padding） |
| **2.4.7** 焦點可見 | 所有可互動元素需可見 focus | `:focus-visible` 3px accent 光圈；卡片 `tabindex=0` |
| **4.1.2** 名稱／角色／狀態 | 動態元件需暴露狀態 | 分類與狀態 demo 按鈕 `aria-pressed`；skeleton `aria-busy`；過期橫幅與錯誤 `role="alert"`；命中筆數 `aria-live="polite"`；搜尋框 `aria-label="搜尋商品名稱或規格"`（input 無可見 label 時）；SVG 一律 `aria-hidden` |

補充：兩主題文字對比目標 ≥4.5:1（`--text` on `--bg`：light `#1f2937/#f7f8fa` ≈ 13.8:1；dark `#e5e7eb/#0f141a` ≈ 14.9:1，皆達標）；動畫於 `prefers-reduced-motion: reduce` 全數關閉。

> **已知取捨（token 固定）**：`--price-down: #18933f` 於淺色白底對比 ≈3.97:1（< 4.5:1），`--price-up` ≈4.07:1——此二值為共用 token，**不可更動**（與 004 平行一致）。緩解：漲跌文字以 600–700 字重呈現且必附「漲／跌／持平／—」文字（滿足 1.4.1，不單靠顏色）；深色主題下兩者對比皆 ≥9.8:1。若日後評審要求嚴格 AA，可在實作層以 `--price-*-strong` 變體供正文使用（不更動共用 token 值）。

---

## 7. 實作建議

1. **Token 先落地**：依 §7.1 建立 CSS 變數（建議 `src/styles/tokens.css` 或 `App.vue :root` 區塊），雙主題以 `data-theme` 切換；元件只引用變數、不硬編碼色值。
2. **資料層**：`useItems` 依 §2.4 實作錯誤分類（fetch／parse）與 `isStale`（>7 天，與 007 共用）；runtime 兩段式 fetch（`api/index.json` → `latest_file` → `api/items/YYYYMMDD[_n].json`），日期制檔名自帶快取失效，無需 query cache-busting。
3. **純函數優先**：`matchesKeyword`／`matchesCondition`／`parseCondition`／`usePriceDelta` 皆純函數，Vitest 直接測（邊界值 12G 命中、缺欄位靜默排除、僅 1 筆 history → delta null）。
4. **搜尋 300ms debounce**：`SearchBar` watch + `setTimeout`；外部清空（clearAll）需同步 input 值。
5. **篩選語意**：僅 `≥`；同欄位重複套用 → 取代（`addCondition` 過濾同 field）；多條件 `every` AND；數值輸入 `inputmode="decimal"`。
6. **空狀態分流**：`emptyKind` 依 keyword→conditions→category 順序判斷；空分類不顯示錯誤、不觸發重試。
7. **卡片鍵盤可操作性**：`tabindex=0` + Enter/Space 觸發 `open`（004 前即可用）；`aria-label` 含商品名與價格。
8. **整合點預留**：`ProductCard` 的 `open`／`toggle-watch`／`toggle-compare` 事件出口在 003 只接 ListingView 佔位 handler，004/005 不得改動元件介面。
9. **斷點**：以 1023／639 實作（§7.6）；建議在 `scripts/` 或 CI 以 Playwright 快照驗證三帶佈局（側欄 240px、水平 chips、單欄卡片）。

---

## 8. 驗收清單

### 8.1 功能（對應 BDD 24 Scenario）

- [ ] 首頁載入後顯示 9 大分類側欄（CPU／主機板／記憶體／顯示卡／SSD／HDD／套裝/準系統／劈發價組合區／記憶卡）＋「全部」
- [ ] 預設顯示全部商品，列表標題顯示「x / 總數 筆」
- [ ] 點分類 → 列表收斂、側欄高亮、URL `?category=<key>`（雙向同步；無效參數視同全部）
- [ ] 深層連結 `?category=GPU` 直接呈現該分類並高亮
- [ ] 全文搜尋（名稱＋spec 欄位、不區分大小寫、字面子字串）；搜尋「9999」不命中歷史價
- [ ] 300ms debounce；僅空白字元視同未搜尋
- [ ] 規格篩選：VRAM≥12G／瓦數≥750W／CPU核數≥8，僅 `≥`、邊界值納入
- [ ] 多條件 AND 交集；同欄位重複套用 → 取代
- [ ] 搜尋＋篩選＋分類三維度同時收斂
- [ ] 清除全部條件 → 保留目前分類、回到該分類完整集合
- [ ] 條件 chips 可單獨移除（✕）

### 8.2 卡片與資料缺漏

- [ ] 卡片顯示：名稱、spec chips、目前價（NT$）、昨日漲跌、sparkline
- [ ] 漲跌：漲紅／跌綠／持平灰，附文字；缺昨日價顯示「—」
- [ ] sparkline < 2 筆顯示「—」（不畫線）
- [ ] 無 spec 欄位商品：名稱搜尋仍命中、結構化篩選靜默排除、不報錯

### 8.3 錯誤與邊界

- [ ] 載入失敗 → 「資料載入失敗」＋重試，側欄/搜尋不白屏
- [ ] 格式錯誤 → 「資料格式錯誤」＋重試（曾載入成功則保留舊資料）
- [ ] 資料過期 >7 天 → 頂部黃色橫幅「資料可能已過期（最後更新：X，台北時間）」，資料仍顯示
- [ ] 搜尋無結果／篩選無結果／空分類三分流，皆有對應清除或回全部路徑
- [ ] 特殊字元關鍵字（如 `RTX+4070 & 12G≥`）字面比對不拋錯

### 8.4 設計與無障礙

- [ ] 兩主題（light/dark）全元件可讀，主文字對比 ≥4.5:1（漲跌語意色為固定 token，淺色 ≈3.97–4.07:1，以字重＋文字緩解，見 §6）
- [ ] 行動端控制 44px、桌面 36px；卡片單欄、側欄水平捲動（≤767）
- [ ] focus-visible 光圈、aria-pressed／aria-busy／role=alert／aria-live 到位
- [ ] 圖示全 inline SVG、`prefers-reduced-motion` 生效
- [ ] 於 Chrome／Safari／Edge 最新版操作正常
