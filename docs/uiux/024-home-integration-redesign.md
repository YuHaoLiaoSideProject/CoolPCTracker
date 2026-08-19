# UI/UX 設計文件 — 024 首頁整合（home-integration-redesign）

> 文件類型：完整規格（合併 ListingView + DashboardView 為統一頁面）
> 對應現有 code：`web/src/views/ListingView.vue`、`web/src/views/DashboardView.vue`
> 互動 mockup：`docs/uiux/024-home-integration-redesign-mockup.html`
> 共用 token：沿用 `web/src/styles/tokens.css`（與 003、004、023 一致）

---

## 1. 現況審計

### 1.1 兩頁功能對比

| # | 現況事實 | ListingView | DashboardView | 合併決策 |
|---|---------|-------------|---------------|---------|
| 1 | 導覽模式 | CategorySidebar（側欄） | CategoryTabs（頂部 Tab） | 統一為 **CategoryTabs** |
| 2 | 搜尋功能 | SearchBar（關鍵字+regex） | ❌ 無 | **保留** SearchBar |
| 3 | 規格篩選 | SpecFilterPanel（條件式） | ❌ 無 | **保留** SpecFilterPanel |
| 4 | 排序功能 | ❌ 無 | DashboardFilterBar（排序下拉） | **整合** 排序下拉至工具列 |
| 5 | 價格篩選 | ❌ 無 | DashboardFilterBar（價格範圍） | **整合** 價格範圍至工具列 |
| 6 | 品牌篩選 | ❌ 無 | DashboardFilterBar（品牌 checkbox） | **整合** 品牌篩選至工具列 |
| 7 | 卡片類型 | ProductCard（完整） | DashboardCard（精簡） | 統一為 **ProductCard**（擴充） |
| 8 | 🥇 徽章 | ❌ 無 | ✅ 有 | **加入** ProductCard |
| 9 | 歷史最低價 | ❌ 無 | ✅ 有 | **加入** ProductCard |
| 10 | Sparkline | ✅ 有 | ✅ 有 | ✅ 已有 |
| 11 | WatchlistButton | ✅ 有 | ✅ 有 | ✅ 已有 |
| 12 | CompareToggle | ✅ 有 | ❌ 無 | ✅ 已有 |
| 13 | 「全部」分類 | ✅ 有 | ❌ 無 | **保留** |
| 14 | Top 10 限制 | ❌ 無 | ✅ 有 | ❌ 棄用（顯示全部） |

### 1.2 共用資源（已可複用）

| 資源 | 路徑 | 狀態 |
|------|------|------|
| `useItems` | `composables/useItems.ts` | ✅ 共用 |
| `tokens.css` | `styles/tokens.css` | ✅ 共用 |
| `ErrorState` | `components/ErrorState.vue` | ✅ 共用 |
| `EmptyState` | `components/EmptyState.vue` | ✅ 共用 |
| `CategoryTabs` | `components/CategoryTabs.vue` | ✅ 可作為統一導覽 |
| `Sparkline` | `components/Sparkline.vue` | ✅ 共用 |
| `WatchlistButton` | `components/WatchlistButton.vue` | ✅ 共用 |

---

## 2. 設計原則

1. **單一入口、統一體驗** — 合併後只有一個首頁路由 `/`，`/dashboard` 重導向至 `/`。
2. **導覽一致** — 統一使用 CategoryTabs（頂部 Tab），移除側欄，減少認知負擔。
3. **漸進式揭露** — 基礎篩選（搜尋+規格）預設可見；進階篩選（排序+價格+品牌）可折疊。
4. **資訊密度平衡** — ProductCard 保留完整功能（Sparkline、追蹤、比較），新增 🥇 + 歷史最低價。
5. **觸控與鍵盤優先** — 行動端觸控目標 44px（WCAG 2.5.5）；`focus-visible` 3px 光圈。

---

## 3. Design Token 表

沿用 `tokens.css`，不可更動。

### 3.1 核心 Token

| Token | Light | Dark | 用途 |
|-------|-------|------|------|
| `--brand` | `#1f6feb` | `#4c8dff` | Tab active、連結、按鈕 |
| `--brand-soft` | `#e8f0fe` | `#1d2f4d` | Tab active 底色、hover 底色 |
| `--bg` | `#f7f8fa` | `#0f141a` | 頁面背景 |
| `--surface` | `#ffffff` | `#161c24` | 卡片、容器表面 |
| `--surface-2` | `#f1f3f5` | `#1e2733` | Skeleton、次要背景 |
| `--border` | `#e5e7eb` | `#2a3340` | 邊框 |
| `--text` | `#1f2937` | `#e5e7eb` | 主文字 |
| `--text-dim` | `#6b7280` | `#8b95a3` | 次要文字 |
| `--radius` | `10px` | `10px` | 卡片圓角 |
| `--radius-sm` | `6px` | `6px` | Tab、按鈕圓角 |
| `--h` | `36px` | `36px` | 桌面控制高度 |
| `--h-mobile` | `44px` | `44px` | 行動控制高度 |
| `--transition` | `0.2s ease` | `0.2s ease` | 過渡動畫 |

### 3.2 整合後衍生樣式

| 項目 | 值 | CSS 對應 | 說明 |
|------|-----|---------|------|
| 工具列高度 | auto | `padding: 12px 14px` | 內部元素 flex 置中 |
| 模式指示器 | 無 | — | 不使用模式切換，統一顯示 |
| 篩選區折疊 | 200ms ease | `max-height` 過渡 | 進階篩選可折疊 |
| 排序下拉 | 36px / 44px | `var(--h)` / `var(--h-mobile)` | 與 Tab 一致 |

---

## 4. 狀態矩陣

覆蓋 8 態：idle / hover / focus / active / disabled / loading / error / 空結果。

### 4.1 CategoryTabs（統一導覽）

| 狀態 | 視覺 | 互動 |
|------|------|------|
| **idle** | 透明底、`text` 色、底部無 border | 可點擊切換分類 |
| **hover** | `brand-soft` 淡底 | 提示可操作 |
| **focus** | `:focus-visible` 3px accent 光圈 | 鍵盤 Enter/Space 觸發 |
| **active** | `brand` 字色、700 weight、底部 2px `brand` border | `aria-selected="true"` |
| **loading** | Tab 文字右側 16px spinner、`opacity: 0.7` | 等待載入完成 |

### 4.2 工具列（搜尋+篩選+排序）

| 狀態 | 視覺 | 互動 |
|------|------|------|
| **idle** | `surface` 底、`border` 邊框 | 元件可操作 |
| **搜尋有值** | SearchBar 顯示 clear 按鈕 | 點擊清除 |
| **篩選啟用** | 顯示「清除篩選」按鈕 + 計數 | 點擊清除全部篩選 |
| **進階篩選折疊** | 「更多篩選 ▼」/「收起 ▲」 | 點擊展開/收起 |

### 4.3 ProductCard（統一卡片）

| 狀態 | 視覺 | 互動 |
|------|------|------|
| **idle** | `surface` 底、`border`、`shadow` | 可點擊進入詳情 |
| **hover** | `border-color: brand` + `shadow-hover` | 提示可操作 |
| **focus** | `:focus-visible` 3px accent 光圈 | 鍵盤 Enter/Space 導航 |
| **active** | 按下瞬間 `surface-2` 底 | 點擊導航至詳情頁 |
| **歷史新低** | 🥇 徽章顯示於卡片右上角 | 資訊標示，無額外互動 |
| **已下架** | 價格區顯示「已下架」文字、`text-dim` 色 | 仍可點擊進入詳情 |
| **error** | 價格區顯示「資料異常」 | 仍可點擊進入詳情 |

---

## 5. RWD 斷點行為表

| 行為 | ≥1024（桌面） | 640–1023（平板） | ≤639（手機） |
|------|--------------|------------------|-------------|
| **整體佈局** | 單欄，`max-width: 1200px` | 單欄 | 單欄 |
| **CategoryTabs** | 水平排列 | 水平捲動 | 水平捲動、44px |
| **工具列** | 水平排列、篩選一行 | 垂直堆疊 | 垂直堆疊 |
| **進階篩選** | 預設展開 | 預設折疊 | 預設折疊 |
| **商品卡片** | `grid auto-fill minmax(300px, 1fr)` | 維持多欄 | 單欄 |
| **控制元件** | 36px | 36px | 44px |

---

## 6. 無障礙清單（WCAG）

| 準則 | 要求 | 對應設計 |
|------|------|----------|
| **1.4.1** 不以顏色單獨傳達 | 🥇 資訊不得只靠 emoji | 🥇 為輔助標示，`aria-label` 含「歷史新低」 |
| **2.5.5** 目標尺寸 | 觸控目標 ≥ 40×40px | 行動端 Tab/按鈕一律 44px |
| **2.4.7** 焦點可見 | 所有可互動元素需可見 focus | `:focus-visible` 3px accent 光圈 |
| **4.1.2** 名稱／角色／狀態 | 動態元件需暴露狀態 | Tab `aria-selected`、Card `role="button"` |

---

## 7. 元件規格

### 7.1 統一工具列（`.home-toolbar`）

- **容器**：`background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 12px 14px; display: flex; flex-direction: column; gap: 12px;`
- **第一列**：SearchBar + 排序下拉選
- **第二列**：進階篩選區（可折疊）— 價格範圍、品牌、規格條件
- **第三列**（篩選啟用時）：結果計數 + 「清除篩選」按鈕

### 7.2 排序下拉選（`.sort-select`）

- **高度**：`var(--h)`（36px desktop）/ `var(--h-mobile)`（44px mobile）
- **選項**：價格高→低、價格低→高、名稱 A→Z、名稱 Z→A
- **樣式**：`padding: 6px 12px; border: 1px solid var(--border); border-radius: 6px;`

### 7.3 進階篩選折疊（`.filter-expand`）

- **觸發按鈕**：`background: none; border: none; color: var(--brand); font-size: 0.85rem; cursor: pointer;`
- **展開動畫**：200ms ease（`max-height` 過渡）
- **預設狀態**：桌面展開、平板/手機折疊

---

## 8. 實作建議

1. **路由**：`/` → `HomeView.vue`（重構自 `ListingView.vue`）；`/dashboard` → 重導向至 `/`
2. **導覽**：移除 `CategorySidebar`，統一使用 `CategoryTabs`（含「全部」分類）
3. **卡片**：`ProductCard` 加入 `isLowest` prop + 🥇 徽章 + 歷史最低價顯示
4. **篩選**：保留 `SearchBar` + `SpecFilterPanel`，整合 `DashboardFilterBar` 的排序功能
5. **清理**：刪除 `DashboardView.vue`、`DashboardCard.vue`、`DashboardFilterBar.vue`

---

## 9. 驗收清單

### 9.1 功能

- [ ] 進入首頁顯示 CategoryTabs（含「全部」分類）
- [ ] 點擊分類 Tab 正確載入該分類商品
- [ ] SearchBar 搜尋功能正常（關鍵字 + regex）
- [ ] SpecFilterPanel 規格篩選正常
- [ ] 排序下拉選正常（價格高→低、低→高、名稱 A→Z）
- [ ] 🥇 歷史新低徽章正確顯示
- [ ] 歷史最低價正確顯示（與目前不同時）
- [ ] 點擊卡片導航至詳情頁
- [ ] WatchlistButton 追蹤功能正常
- [ ] CompareToggle 比較功能正常
- [ ] `/dashboard` 重導向至 `/`

### 9.2 響應式

- [ ] Desktop（≥1024）：多欄卡片、Tab 水平排列
- [ ] Tablet（640–1023）：多欄卡片、Tab 水平捲動
- [ ] Mobile（≤639）：單欄卡片、Tab 44px

### 9.3 狀態

- [ ] 骨架屏 shimmer 動畫正常
- [ ] 載入失敗 → ErrorState + 重試
- [ ] 空分類 → EmptyState
- [ ] 篩選無結果 → EmptyState

### 9.4 設計與無障礙

- [ ] 兩主題（light/dark）全元件可讀
- [ ] 行動端控制 44px、桌面 36px
- [ ] focus-visible 光圈到位
- [ ] 圖示全 inline SVG

---

## 10. 檔案變更清單

| 檔案 | 變更類型 | 說明 |
|------|---------|------|
| `web/src/views/HomeView.vue` | **新增** | 統一首頁（重構自 ListingView） |
| `web/src/views/ListingView.vue` | **刪除** | 功能已移入 HomeView |
| `web/src/views/DashboardView.vue` | **刪除或重導向** | `/dashboard` → `/` |
| `web/src/components/ProductCard.vue` | **修改** | 加入 🥇 + 歷史最低價 |
| `web/src/components/DashboardCard.vue` | **刪除** | 功能已被 ProductCard 取代 |
| `web/src/components/CategoryTabs.vue` | **修改** | 加入「全部」分類 |
| `web/src/components/DashboardFilterBar.vue` | **刪除** | 排序功能整合進工具列 |
| `web/src/composables/useDashboardFilters.ts` | **整合** | 排序邏輯移入 useFilters |
| `web/src/router/index.ts` | **修改** | `/dashboard` 重導向 |
