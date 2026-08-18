# 開發方案決策文件：#017 Dashboard — 查看分類最便宜商品

> **性質**：前端功能層技術評估（tech-assessment-generator 引導，非互動模式產出）
> **對應**：GitHub Issue **#17** `feat(P1): Dashboard — 查看分類最便宜商品`
> **範圍**：`web/src/`（前端新增 DashboardView、useDashboard composable、DashboardCard 元件）
> **上游文件**：`docs/interaction-flows/017-dashboard-items.md`（主輸入）
> **決策方式**：基於上游文件 + 現有專案架構推導，**不提問**；所有決策點由評估者給定推薦結論，待實作前的 spec/review 階段正式確認

---

## 📌 決策摘要

| 項目 | 內容 |
|------|------|
| **最終方案** | **方案 D「獨立 DashboardView + useDashboard composable + ProductCard 複用」**：新增 `DashboardView.vue`（路由 `/dashboard`）、`useDashboard.ts` composable（排序 + 取 Top 10 + 歷史最低價計算）、`DashboardCard.vue` 元件（精簡版 ProductCard，含歷史最低價徽章）；資料來源直接複用 `useItems`（module-level singleton），不建立獨立 fetch 邏輯 |
| **決策日期** | 2026-08-17 |
| **決策前提** | ① Dashboard 為獨立頁面，與 ListingView 分離；② 資料來源為靜態 JSON（`api/items/{g}.json`），無後端；③ 無 Pinia store，composable 模式；④ 需顯示歷史最低價（從 item.history 計算）；⑤ 分類 Tab 切換，每分類前 10 名 |
| **核心效益** | 複用 `useItems` singleton 避免重複 fetch；`useDashboard` 純前端排序（<1ms）；`DashboardCard` 精簡 DOM 減少重繪；骨架屏 + error state 與 ListingView 一致的 UX 模式 |
| **共識程度** | ✅ 非互動推導，共識待 spec/review 階段確認（§6.3） |

---

## 1. 需求回顧

### 1.1 使用者／Issue 訴求

> 「讓使用者在 Dashboard 看到每個分類中最便宜的商品列表，一目瞭然掌握市場行情。」

**拆解出的核心需求**：

| 需求項 | 說明 | 來源 |
|--------|------|------|
| 分類 Tab 切換 | 以 Tab 顯示各分類（CPU、顯示卡、記憶體…），點擊切換 | IF §4 步驟 2 |
| 每分類 Top 10 | 按價格低→高排序，取前 10 名最便宜商品 | IF §4 步驟 3 |
| 歷史最低價 | 每張卡片顯示歷史最低價，達成時標示 🥇 徽章 | IF §4 步驟 3、驗收清單 |
| 骨架屏載入 | 資料載入中顯示全頁骨架屏（skeleton loading） | IF §4 步驟 1 |
| 錯誤重試 | API 失敗顯示錯誤頁面 + 重試按鈕 | IF §5 |
| 空狀態 | 分類無商品顯示空狀態 | IF §5 |
| 直接連結 | 支援 `/#/dashboard` 直接訪問 | IF §2.1 |

### 1.2 需求假設（評估者由上游文件與現況推導）

| 假設 | 內容 | 依據 |
|------|------|------|
| H1 | Dashboard 為獨立頁面（不嵌入 ListingView），路由 `/dashboard` | IF §2.1、驗收「Dashboard 頁面可正常訪問」 |
| H2 | 資料來源與 ListingView 相同（`api/items/{g}.json`），共用 `useItems` singleton | 專案架構：module-level singleton 模式 |
| H3 | 排序邏輯在前端執行（靜態 JSON，無後端排序 API） | 專案無後端 server |
| H4 | 歷史最低價從 `item.history` 計算（`Math.min(...history.map(p => p.p))`） | 已有 `usePriceHistory` 的 `stats.low` 邏輯 |
| H5 | Dashboard 不需要搜尋/篩選功能（純展示最便宜 Top 10） | IF 未提及搜尋需求 |
| H6 | 分類 Tab 預設選取第一個分類（依 categories 順序） | IF §4 步驟 2 |

### 1.3 非需求

- ❌ 不需要搜尋/篩選功能（那是 ListingView 的職責）
- ❌ 不需要 Watchlist/Compare 功能（可選 future enhancement）
- ❌ 不需要拖曳排序或自訂分類順序
- ❌ 不需要無限滾動（Top 10 固定數量）

---

## 2. 現況分析

### 2.1 可複用的現有模組

| 模組 | 檔案 | 可複用性 | 備註 |
|------|------|---------|------|
| `useItems` | `composables/useItems.ts` | ✅ **直接複用** | module-level singleton；index + lazy 分類載入；`items`、`categories`、`loading`、`error`、`retry` 全部可用 |
| `usePriceDelta` | `composables/usePriceDelta.ts` | ✅ **直接複用** | `currentPrice`、`deltaClass`、`deltaText` 可用於卡片 |
| `usePriceHistory` | `composables/usePriceHistory.ts` | ⚠️ **部分複用** | `stats.low`（歷史最低價）可直接取用；但需傳入 `Ref<PricePoint[]>` |
| `ProductCard` | `components/ProductCard.vue` | ⚠️ **可參考但需客製** | ProductCard 包含 WatchlistButton、CompareToggle、Sparkline 等 Dashboard 不需要的元素；建議新建精簡版 |
| `ErrorState` | `components/ErrorState.vue` | ✅ **直接複用** | 錯誤頁面 + 重試按鈕 |
| `EmptyState` | `components/EmptyState.vue` | ✅ **直接複用** | 空狀態顯示 |
| `formatPrice` | `utils/format.ts` | ✅ **直接複用** | 價格千分位格式化 |
| `specChipTexts` | `composables/usePriceDelta.ts` | ✅ **直接複用** | 規格 chips 顯示 |

### 2.2 與 ListingView 的差異

| 面向 | ListingView | Dashboard |
|------|------------|-----------|
| 目的 | 全商品瀏覽（所有分類） | 各分類最便宜 Top 10 |
| 分類切換 | 側欄（CategorySidebar） | Tab 列表 |
| 排序 | 不排序（依 API 預設順序） | 按價格低→高 |
| 數量限制 | 無限制（全量顯示） | 每分類 Top 10 |
| 搜尋/篩選 | 有（SearchBar + SpecFilterPanel） | 無 |
| 歷史最低價 | 不顯示 | 顯示（🥇 徽章） |
| Watchlist/Compare | 有（WatchlistButton + CompareToggle） | 可選（initial release 不含） |

---

## 3. 候選方案

### 方案 D（推薦）：獨立 DashboardView + useDashboard composable

**架構**：
```
router/index.ts
  → /dashboard → DashboardView.vue（懶載入）
    ├── useItems()（singleton，複用現有）
    ├── useDashboard(items, activeCategoryId)（新 composable：排序 + Top 10 + 歷史最低價）
    ├── DashboardCard.vue（新元件：精簡版卡片）
    ├── ErrorState（複用）
    └── EmptyState（複用）
```

**資料流**：
```
useItems().bootstrap()        → index.json → categories[]
useItems().loadCategory(id)   → api/items/{g}.json → items[]
useDashboard()                → 排序 + Top 10 + 歷史最低價 → dashboardItems[]
DashboardCard                 → formatPrice + usePriceDelta + 🥇徽章
```

**useDashboard composable 職責**：
- 接收 `items: Ref<Item[]>` + `activeCategoryId: Ref<string | null>`
- 計算 `dashboardItems: computed<Item[]>`：過濾目前分類 → 按 `currentPrice` 升冪 → `slice(0, 10)`
- 計算 `categoryLowest: computed<Map<string, { price: number; itemId: string }>>`：每分類歷史最低價（供 🥇 徽章）

### 方案 L（保守）：直接在 DashboardView 內聯排序邏輯

不新建 composable，排序/Top 10/歷史最低價直接寫在 `<script setup>` 的 computed 中。

- **優點**：最簡單、一個檔案搞定
- **缺點**：邏輯與元件耦合、不易測試、若未來 Dashboard 需擴充（如加入 Compare）則重構成本高
- 結論：初期可行但不符合專案的 composable 分離 pattern（所有 view 都有獨立 composable）

### 方案 P（激進）：建立獨立 useDashboardItems composable（含獨立 fetch）

不複用 `useItems` singleton，自行 fetch index + 分類檔、自行管理載入狀態。

- **優點**：完全獨立、不影響 ListingView
- **缺點**：重複 fetch 相同資料（index.json + 分類檔）、增加網路請求、違反 singleton 節省資源的設計意圖、維護兩套 fetch 邏輯
- 結論：過度隔離，犧牲效能與維護性

---

## 4. 權衡評估

### 4.1 權衡矩陣（1–5 分，5 最佳）

| 維度 | L 保守（內聯） | **D 獨立 composable** | P 獨立 fetch |
|---|:---:|:---:|:---:|
| 🎯 需求符合度 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| ⚡ 開發速度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| 🔧 維護成本 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 📦 效能（網路/渲染） | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 🧩 模組化/可測試性 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 🔄 複用性（跨頁面） | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 👥 團隊熟悉度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **總分** | **22** | **32** | **23** |

### 4.2 關鍵取捨

**取捨 #1：ProductCard 複用 vs 新建 DashboardCard**

- **選項 A**：直接使用 `ProductCard`，透過 props 控制顯示/隱藏 WatchlistButton、CompareToggle、Sparkline
- **選項 B**：新建 `DashboardCard`，精簡 DOM（只顯示名稱、價格、歷史最低價、規格 chips）

**決策（D1）：取 B（新建 DashboardCard）**
- ProductCard 的 DOM 結構為 ListingView 設計（含 Sparkline、WatchlistButton、CompareToggle），Dashboard 不需要這些元素
- 強行複用會增加 conditional rendering（`v-if`）和 props 傳遞，反而增加複雜度
- DashboardCard 可保持精簡（~100 行 template），渲染效能更好
- 若未來 Dashboard 需加入 Watchlist/Compare，可再擴充 DashboardCard 或回頭整合 ProductCard

**取捨 #2：Tab 實作方式**

- **選項 A**：自訂 Tab 元件（純 CSS + radio input 或 button group）
- **選項 B**：使用第三方 UI library（如 PrimeVue、Vuetify）

**決策（D2）：取 A（自訂 Tab）**
- 專案無 UI library 依賴（純 Vue 3 + 自訂元件），不引入新依賴
- Tab 邏輯簡單（button group + active state），不需要第三方
- 可直接在 DashboardView 內實作（或提取為小型 `CategoryTabs.vue` 元件）

**取捨 #3：骨架屏實作方式**

- **選項 A**：全頁骨架屏（整頁 CSS 動畫，資料載入完成後淡出）
- **選項 B**：分區域骨架屏（Tab 區域 + 列表區域各自 skeleton）

**決策（D3）：取 A（全頁骨架屏）**
- 與 ListingView 的載入模式一致（IF §4 步驟 1：「顯示全頁骨架屏」）
- 實作簡單：一個 `DashboardSkeleton.vue` 元件，`v-if="loading"` 顯示
- 資料載入完成後用 CSS transition 淡出（`opacity` + `transition`）

**取捨 #4：歷史最低價計算位置**

- **選項 A**：在 `useDashboard` composable 內計算（每分類的 `categoryLowest` Map）
- **選項 B**：在 `DashboardCard` 元件內計算（每張卡片各自算 `Math.min(...history.map(p => p.p))`）

**決策（D4）：取 A（composable 內計算）**
- 集中計算避免重複（每分類 Top 10 各算一次 `Math.min`）
- `categoryLowest` Map 可供 DashboardCard 直接取用（判斷 🥇 徽章）
- 計算成本極低（Top 10 × history ≤2 點 = 20 次比較），但保持邏輯分離更清晰

---

## 5. 決策理由

### 5.1 為什麼選方案 D
1. **符合專案既有 pattern**：所有 view 都有獨立 composable（useItems、useFilters、useWatchlist、useCompare）；Dashboard 遵循此 pattern 最一致
2. **複用 useItems singleton 避免重複 fetch**：index.json + 分類檔已由 useItems 載入並快取；Dashboard 直接消費 `items` ref，零額外網路請求
3. **模組化可測試**：`useDashboard` 為純函數（接收 ref、回傳 computed），可獨立單測；DashboardCard 為純展示元件，可用 @vue/test-utils 測試

### 5.2 為什麼放棄其他方案
| 方案 | 放棄理由 |
|---|---|
| **L 保守** | 邏輯與元件耦合、不易測試；不符合專案 composable 分離 pattern；若 Dashboard 擴充（加入 Compare、Watchlist）需重構 |
| **P 獨立 fetch** | 重複 fetch 相同資料（index + 分類檔）、增加網路請求（靜態 JSON 每次 fetch ~35KB）、違反 singleton 節省資源設計；維護兩套 fetch 邏輯（useItems + useDashboardItems）成本高 |

### 5.3 分階段執行策略

| 階段 | 內容 | 依賴 |
|---|---|---|
| **Phase 1** | `useDashboard` composable（排序 + Top 10 + 歷史最低價計算）+ 單測 | —（可先做，獨立於 UI） |
| **Phase 2** | `DashboardCard` 元件（精簡版卡片）+ `DashboardSkeleton`（骨架屏）+ 單測 | Phase 1 |
| **Phase 3** | `DashboardView.vue`（整合 Tab + useDashboard + DashboardCard + ErrorState + EmptyState）+ 路由註冊 | Phase 1–2 |
| **Phase 4** | 整合測試（E2E：Tab 切換、Top 10 排序、歷史最低價顯示、錯誤重試） | Phase 3 |

---

## 6. 行動計畫

### 6.1 目標架構

```
web/src/
  router/index.ts                    # 新增 /dashboard 路由（懶載入）
  views/
    DashboardView.vue                # 【新增】Dashboard 頁面
  composables/
    useDashboard.ts                  # 【新增】排序 + Top 10 + 歷史最低價
  components/
    DashboardCard.vue                # 【新增】精簡版商品卡片
    DashboardSkeleton.vue            # 【新增】骨架屏
  types/
    item.ts                          # （不變）Item 型別已足夠
  utils/
    format.ts                        # （不變）formatPrice 已足夠
```

### 6.2 任務拆分

| # | 任務 | 檔案 | 依賴 |
|---|------|------|------|
| T1 | `useDashboard` composable：接收 `items` + `activeCategoryId`，計算 `dashboardItems`（過濾分類 → 按 currentPrice 升冪 → slice(0,10)）+ `categoryLowest`（每分類歷史最低價 Map）；含型別定義 `DashboardItem`（擴展 Item 加 `isLowest: boolean`） | `composables/useDashboard.ts`、`composables/__tests__/useDashboard.test.ts` | — |
| T2 | `DashboardCard` 元件：顯示商品名稱、目前價格（`usePriceDelta`）、歷史最低價（`formatPrice`）、🥇 徽章（`isLowest`）、規格 chips（`specChipTexts`）、已下架標籤；點擊 → 導航至商品詳情 | `components/DashboardCard.vue`、`components/__tests__/DashboardCard.test.ts` | T1 |
| T3 | `DashboardSkeleton` 元件：Tab 區域 skeleton + 列表區域 skeleton（10 個卡片佔位）；CSS 動畫（pulse/shimmer） | `components/DashboardSkeleton.vue` | — |
| T4 | `DashboardView.vue`：Tab 列表（categories → button group）+ useDashboard + DashboardCard 列表 + ErrorState + EmptyState + DashboardSkeleton；Tab 切換呼叫 `loadCategory(id)` | `views/DashboardView.vue`、`views/__tests__/DashboardView.test.ts` | T1–T3 |
| T5 | 路由註冊：`/dashboard` → 懶載入 `DashboardView`（`() => import(...)` 與 ProductDetailView 一致） | `router/index.ts` | T4 |
| T6 | 導覽列加入 Dashboard 連結（若尚無） | `App.vue` 或導覽元件 | T5 |
| T7 | E2E 測試：Tab 切換、Top 10 排序驗證、歷史最低價顯示、骨架屏→列表轉場、錯誤重試 | `e2e/` 或 `playwright/` | T4–T6 |

### 6.3 決策點（非互動推導，待 spec/review 正式確認）

| 決策點 | 選項 | 評估者結論（待確認） |
|---|---|---|
| **D1** DashboardCard vs 複用 ProductCard | a) 複用 ProductCard（props 控制隱藏元素）；b) **新建 DashboardCard（精簡版）** | ✅ **b 新建**：ProductCard 含 Sparkline/WatchlistButton/CompareToggle 等 Dashboard 不需要的元素；強行複用增加 conditional rendering 複雜度 |
| **D2** Tab 實作方式 | a) **自訂 Tab（button group）**；b) 第三方 UI library | ✅ **a 自訂**：專案無 UI library、Tab 邏輯簡單、不引入新依賴 |
| **D3** 骨架屏方式 | a) **全頁骨架屏**；b) 分區域骨架屏 | ✅ **a 全頁**：與 ListingView 載入模式一致（IF §4 步驟 1）；實作簡單 |
| **D4** 歷史最低價計算位置 | a) **composable 內計算**；b) 元件內各自計算 | ✅ **a composable**：集中計算避免重複、可供多處取用、邏輯分離 |
| **D5** Dashboard 是否顯示 Sparkline（迷你趨勢圖） | a) 顯示（複用 Sparkline 元件）；b) **不顯示**（純價格數字） | ✅ **b 不顯示**：Top 10 為快速概覽，Sparkline 增加 DOM 複雜度且歷史僅 ≤2 點（無趨勢意義）；詳情頁已有完整趨勢圖 |
| **D6** Tab 預設選取邏輯 | a) 預設第一個分類（依 categories 順序）；b) 預設「全部」（顯示所有分類 Top 10 混合） | ✅ **a 第一個分類**：IF §4 步驟 2 明確「預設選取第一個分類」；「全部」需跨分類聚合排序（不同分類價格基準不同，混排無意義） |
| **D7** Dashboard 是否支援 Watchlist/Compare | a) 初版不含（純展示）；b) 初版即含 | ✅ **a 初版不含**：IF 未提及、降低初版複雜度；可作為 future enhancement 加入 DashboardCard |

---

## 7. 風險登錄

| 風險 | 可能性 | 影響 | 緩解 |
|------|--------|------|------|
| `useItems` singleton 載入分類時機與 Dashboard 預設分類不同步 | 中 | 中 | DashboardView watch `categories` 變化後再呼叫 `loadCategory`（與 ListingView 的 `applyUrlToState` 模式一致） |
| 歷史最低價計算與 `usePriceHistory.stats.low` 不一致 | 低 | 中 | 共用同一事實來源（`item.history`）；`useDashboard` 直接計算 `Math.min(...)` 與 `usePriceHistory` 邏輯等價；可加 equivalence test |
| `loadCategory` 併發（快速切換 Tab）導致 stale data | 低 | 低 | `useItems.loadCategory` 已有快取機制（`loadedIds.has(id)` → 立即切換）；in-flight 去重（`inFlight` Map） |
| 骨架屏→列表轉場動畫不流暢 | 低 | 低 | CSS transition（opacity + transform）；避免 layout shift（骨架屏與列表佔同高度） |
| Dashboard 路由懶載入 chunk 過大 | 低 | 低 | DashboardView 依賴輕量元件（無 lightweight-charts）；chunk 預估 <10KB gzipped |

---

## 📝 決策後續

- 本文件已存至 `docs/tech-decisions/017-dashboard-items.md`，應納入版本控制。
- **決策待確認**：§6.3 七個決策點（D1–D7）為非互動推導結論，建議在 development-spec-generator／loop-review 階段正式確認後展開 Phase 1–4。
- 實作以 `useItems` singleton 為資料基礎；若未來 Dashboard 需要與 ListingView 不同的資料範圍（如只載入特定分類），可擴充 `useItems` 的 `loadCategory` 調度，但不建立獨立 fetch。
- 建議 1 個月後回顧：Dashboard 使用率、是否需加入 Watchlist/Compare 功能、Tab 切換效能（分類數成長時）。
