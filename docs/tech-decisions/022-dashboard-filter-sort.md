# Tech Decision — Dashboard 商品篩選與排序（022）

> **狀態**：✅ 已完成
> **功能編號**：022 — dashboard-filter-sort
> **Issue**：#22
> **上游文件**：
> - `docs/interaction-flows/022-dashboard-filter-sort.md`（操作流程）
> - `docs/bdds/022-dashboard-filter-sort.feature`（BDD 場景）
> **關聯 Tech Decision**：#017（Dashboard 展示邏輯）、#018（規格分組）、#019（分類 Tab）

---

## 1. 排序邏輯實作位置

### 問題

`useDashboard.ts` 目前硬編碼 `sort by price ascending + slice(0, 10)`。需要支援 3 種排序方式（價格低→高 / 高→低 / 最近更新），且排序須在篩選後執行。

### 選項

| 選項 | 描述 |
|------|------|
| **A. 擴充 useDashboard.ts** | 在現有 composable 新增 `sortMode` ref + 排序 switch |
| **B. 新增 useDashboardSort.ts** | 獨立 composable，接收 items + sortMode，回傳 sortedItems |
| **C. 在 DashboardView 內聯處理** | 直接在 `<script setup>` 中 computed 排序 |

### 取捨

- **A**：改動最小，但 useDashboard 已承擔「展示邏輯 + 分類切換 + 分組重置」，職責過重
- **B**：職責分離清晰，排序邏輯可獨立測試；但多一層 composable 呼叫
- **C**：最簡單，但排序邏輯散落在 View 中，不易測試

### 結論：**B — 新增 useDashboardSort.ts**

理由：
- 排序邏輯與篩選邏輯高度關聯（排序在篩選之後），獨立 composable 便於組合
- 與 useSpecGroups 同層級（都是 transform pipeline 的一步），風格一致
- BDD @sort 場景（3 個）可對應獨立的 unit test

---

## 2. 價格區間篩選器 UI

### 問題

需要讓使用者輸入價格下限與上限。互動流程指定「自動交換上下限」。

### 選項

| 選項 | 描述 |
|------|------|
| **A. 兩個 `<input type="number">`** | 下限 + 上限，各為獨立輸入框 |
| **B. `<input type="range">` 雙滑塊** | 滑桿控制價格範圍 |
| **C. 單一 `<input>` 搭配下拉** | 輸入一個值 + 選擇「以上/以下/之間」 |

### 取捨

- **A**：實作最簡單，鍵盤輸入精確；但需自行處理 auto-swap 邏輯
- **B**：視覺直觀，但範圍依賴資料分佈（price range 需先計算），mobile 操作不佳
- **C**：UX 彈性高，但操作步驟多

### 結論：**A — 兩個 `<input type="number">`**

理由：
- 電腦零組件價格範圍大（$500 ~ $60,000+），滑桿精度不足
- 手機端 number input 有原生數字鍵盤
- Auto-swap 邏輯簡單（watch 兩個 ref，若 min > max 則 swap）
- BDD @filter-price 場景（4 個）皆以數字輸入描述

---

## 3. 品牌篩選器 UI

### 問題

品牌來源為 `item.spec.brand`，數量不固定（依分類而異，可能 3~20+ 個）。

### 選項

| 選項 | 描述 |
|------|------|
| **A. Checkbox List** | 所有品牌以 checkbox 列出，垂直排列 |
| **B. Dropdown Multi-select** | 下拉選單 + 多選 checkbox |
| **C. Chip Toggle** | 品牌以 Chip 按鈕顯示，點擊切換選取 |

### 取捨

- **A**：一覽無遺，品牌少時最佳；品牌多時需捲動
- **B**：節省空間，但隱藏已選品牌，需額外 UI 顯示已選
- **C**：與 SpecGroupChips 風格一致；但品牌多時視覺擁擠

### 結論：**A — Checkbox List（帶垂直捲動限制）**

理由：
- Dashboard 主要分類（記憶體、顯示卡、SSD、HDD、CPU、主機板、電源）品牌數量通常 3~10 個
- Checkbox 是最直覺的多選 UI（已選/未選一目了然）
- 限制最大高度 + `overflow-y: auto` 處理品牌過多的情境
- 與 BDD @filter-brand 場景（勾選/取消勾選）對齊

---

## 4. 篩選狀態管理

### 問題

需要管理：sortMode、priceMin、priceMax、selectedBrands。這些狀態應放在哪裡？

### 選項

| 選項 | 描述 |
|------|------|
| **A. 擴充 useFilters.ts** | 在現有 useFilters 中新增 sortMode / priceRange / brands |
| **B. 新增 useDashboardFilters.ts** | 獨立 composable 管理 Dashboard 特有的篩選 |
| **C. 用 Pinia store** | 新增 dashboardFilter store 管理狀態 |

### 取捨

- **A**：useFilters 已有 keyword + conditions，加入更多狀態會使其臃腫；且 Dashboard 目前未使用 useFilters
- **B**：職責分離，Dashboard 篩選邏輯獨立；但與 useFilters 可能有重疊
- **C**：全域狀態便於跨頁面共享；但 Dashboard 篩選是頁面級功能，不需要跨頁

### 結論：**B — 新增 useDashboardFilters.ts**

理由：
- Dashboard 篩選（價格/品牌/排序）與 Listing 頁面的 useFilters（關鍵字/規格條件）是不同維度
- useFilters 的 keyword + SpecCondition 已足夠服務 Listing 頁面
- Dashboard 篩選是純前端 client-side 過濾，不需要與後端 API 互動
- 獨立 composable 便於單元測試（mock items 即可）

---

## 5. 與現有 useFilters 的關係

### 問題

`useFilters.ts` 已實作 keyword + SpecCondition 邏輯，但 DashboardView 並未使用它。022 的篩選（價格區間 + 品牌）是否應合併進 useFilters？

### 選項

| 選項 | 描述 |
|------|------|
| **A. 合併到 useFilters** | 將 priceRange / brands 加入 useFilters，Dashboard 也使用 useFilters |
| **B. 獨立使用** | useDashboardFilters 管理 Dashboard 篩選，useFilters 繼續服務 Listing |
| **C. 抽出共用 core** | 將 useFilters 重構為共用 core + 頁面特化 wrapper |

### 取捨

- **A**：useFilters 會變得更複雜，但狀態統一；需修改 DashboardView 改用 useFilters
- **B**：最簡單，兩個 composable 各司其職；但若未來需要統一篩選邏輯需再重構
- **C**：長期最佳，但改動量大，影響 003 已實作的 Listing 功能

### 結論：**B — 獨立使用**

理由：
- Dashboard 和 Listing 的篩選維度完全不同（價格/品牌 vs 關鍵字/規格條件）
- 強行合併會使 useFilters 職責模糊
- 未來若有需求（如「篩選狀態同步到 URL」），可再重構
- 最小改動原则：不影響 003 已穩定的 Listing 功能

---

## 6. 顯示篩選結果數量

### 問題

BDD @count 場景要求顯示「顯示 N 件商品」。數量應顯示在哪裡？

### 選項

| 選項 | 描述 |
|------|------|
| **A. 篩選控制項下方** | 在排序/篩選 UI 與商品列表之間 |
| **B. 商品列表上方** | 緊貼在 grid 上方 |
| **C. 篩選控制項內** | 嵌入排序下拉選單旁 |

### 結論：**A — 篩選控制項下方**

理由：
- 視覺層次清晰：控制項 → 數量 → 商品列表
- 與 BDD 場景描述一致（篩選套用後顯示數量）

---

## 7. 清除篩選按鈕位置與行為

### 問題

BDD @clear-filters 場景要求「清除篩選」按鈕。按鈕何時顯示？清除哪些狀態？

### 決策

- **顯示時機**：任何篩選條件有值時（priceMin / priceMax / selectedBrands 任一非空）
- **清除範圍**：清除 priceMin、priceMax、selectedBrands；**不影響 sortMode**（排序是獨立行為）
- **位置**：篩選控制項區域的右側，與數量顯示同行
- **例外**：BDD 場景「篩選無結果時清除篩選恢復列表」要求清除後恢復完整清單

> ⚠️ 互動流程 §5 異常處理提到「重置所有篩選」，此處明確不包含 sortMode，因為排序是使用者主動選擇的展示偏好，不屬於「篩選」。

---

## 8. 空狀態元件共用

### 問題

BDD @empty-state 場景要求篩選無結果時顯示空狀態。應使用現有 `EmptyState.vue` 還是新增？

### 決策

- **共用 EmptyState.vue**，新增 `kind="filter"` 變體
- 訊息：「無符合商品」
- 附帶「清除篩選」按鈕（emit `clear` 事件）
- 與現有 `kind="category"` 並列，不新增元件

---

## 決策摘要

| # | 決策 | 結論 | BDD 場景依據 |
|---|------|------|-------------|
| D1 | 排序邏輯實作位置 | 新增 useDashboardSort.ts | @sort × 3 |
| D2 | 價格篩選器 UI | 兩個 `<input type="number">` | @filter-price × 4 |
| D3 | 品牌篩選器 UI | Checkbox List | @filter-brand × 3 |
| D4 | 篩選狀態管理 | 新增 useDashboardFilters.ts | @filter-intersection × 3, @clear-filters × 2 |
| D5 | 與 useFilters 的關係 | 獨立使用，不合併 | 全局架構考量 |
| D6 | 結果數量顯示位置 | 篩選控制項下方 | @count × 2 |
| D7 | 清除篩選行為 | 清除篩選，保留排序 | @clear-filters × 2 |
| D8 | 空狀態元件 | 共用 EmptyState + kind="filter" | @empty-state × 2 |
