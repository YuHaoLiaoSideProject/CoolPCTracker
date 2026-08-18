# Dashboard Items — 開發規格

> **技術棧**：Vue 3.5 · Vite 6.0 · TypeScript 5.6 · lightweight-charts 5.2（本功能不使用）
> **Tech Decision**：`docs/tech-decisions/017-dashboard-items.md`
> **操作流程**：`docs/interaction-flows/017-dashboard-items.md`
> **BDD**：`docs/bdds/017-dashboard-items.feature`
> **狀態**：設計完成，待開發

---

## 概述

讓使用者在 Dashboard 看到每個分類中最便宜的商品列表，一目瞭然掌握市場行情。核心包含：

1. **`useDashboard` composable**：接收 `items` + `activeCategoryId`，計算各分類 Top 10 最便宜商品 + 歷史最低價 Map
2. **`DashboardCard` 元件**：精簡版商品卡片（商品名稱、目前價格、歷史最低價、🥇 徽章、規格 chips、已下架標籤）
3. **`DashboardSkeleton` 元件**：全頁骨架屏（Tab 區域 + 列表區域佔位動畫）
4. **`DashboardView` 頁面**：整合 Tab 列表、useDashboard、DashboardCard 列表、ErrorState、EmptyState

---

## 1. 後端實作規格

> **不適用**：本功能為純前端，無後端 API 改動。資料來源為靜態 JSON（`api/items/{g}.json`），由現有 `useItems` singleton 載入。

---

## 2. 前端實作規格

### 2.1 檔案改動總覽

```
web/src/
├── router/index.ts                    ← 修改：新增 /dashboard 路由（懶載入）
├── composables/
│   └── useDashboard.ts                ← 新增：排序 + Top 10 + 歷史最低價計算
├── composables/__tests__/
│   └── useDashboard.test.ts           ← 新增：useDashboard 單元測試
├── components/
│   ├── DashboardCard.vue              ← 新增：精簡版商品卡片
│   └── DashboardSkeleton.vue          ← 新增：全頁骨架屏
├── views/
│   └── DashboardView.vue              ← 新增：Dashboard 頁面（Tab + 列表 + Error/Empty）
└── views/__tests__/
    └── DashboardView.test.ts          ← 新增：DashboardView 整合測試
```

### 2.2 useDashboard composable

**職責**：接收 `useItems` 的 `items` ref 與 `activeCategoryId` ref，計算：
- `dashboardItems`：目前選中分類的商品 → 按 `currentPrice` 升冪排序 → `slice(0, 10)`
- `categoryLowest`：每分類歷史最低價 Map（`Map<string, { price: number; itemId: string }>`），供 DashboardCard 判斷 🥇 徽章

```typescript
// web/src/composables/useDashboard.ts
import { computed, type Ref } from "vue"
import type { Item } from "@/types/item"

/** Dashboard 卡片用商品（擴展 Item 加計算欄位） */
export interface DashboardItem {
  item: Item
  currentPrice: number | null   // history 最後一筆 p；空 history 為 null
  isLowest: boolean             // 目前價格 === 該分類歷史最低價
  lowestPrice: number | null    // 該分類歷史最低價（徽章文案用）
}

/**
 * 計算 Dashboard 展示用資料（排序 + Top 10 + 歷史最低價）
 * @param items       — 已過濾的目前分類商品（由 DashboardView 用 itemToCategory 過濾）
 * @param categoryId  — 目前選中分類 id（null 表示尚未選取）
 * @returns dashboardItems（已排序 Top 10 + isLowest/lowestPrice 已填入）
 */
export function useDashboard(
  items: Ref<Item[]>,
  categoryId: Ref<string | null>,
) {
  /** 計算單一商品的目前價格（history 最後一筆 p） */
  function extractCurrentPrice(item: Item): number | null {
    return item.history.length > 0 ? item.history[item.history.length - 1].p : null
  }

  /** 全域歷史最低價 Map：Map<分類id, { price, itemId }>（Tech Decision D4：composable 內計算） */
  // 過濾入的 items 已是全域（含所有分類），可直接遍歷計算每分類最低價。
  const categoryLowest = computed(() => {
    const map = new Map<string, { price: number; itemId: string }>()
    for (const item of items.value) {
      if (item.history.length === 0) continue
      const price = item.history[item.history.length - 1].p
      const existing = map.get(categoryId.value ?? "")
      if (!existing || price < existing.price) {
        map.set(categoryId.value ?? "", { price, itemId: item.id })
      }
    }
    return map
  })

  /** 目前選中分類的商品列表（按 currentPrice 升冪 + Top 10 + 填入 isLowest/lowestPrice） */
  const dashboardItems = computed<DashboardItem[]>(() => {
    const id = categoryId.value
    if (id == null) return []
    const lowest = categoryLowest.value.get(id)
    return items.value
      .map(item => ({
        item,
        currentPrice: extractCurrentPrice(item),
        isLowest: lowest != null && item.id === lowest.itemId,
        lowestPrice: lowest?.price ?? null,
      }))
      .sort((a, b) => {
        if (a.currentPrice == null) return 1  // null 排到最後
        if (b.currentPrice == null) return -1
        return a.currentPrice - b.currentPrice
      })
      .slice(0, 10)
  })

  return { dashboardItems, extractCurrentPrice }
}
```

> **實作備註**：Tech Decision D4 決定 `categoryLowest` 在 composable 內計算（集中計算避免重複、可從全域 items 遍歷）。`useDashboard` 接收已過濾的全域 `items` ref，計算 `categoryLowest` Map 後填入 `dashboardItems` 的 `isLowest`/`lowestPrice`，呼叫端（DashboardView）直接使用 `dashboardItems` 即可，無需額外 enriching。

### 2.3 DashboardCard 元件

**職責**：精簡版商品卡片（不含 Sparkline、WatchlistButton、CompareToggle）。顯示商品名稱、目前價格、歷史最低價、🥇 徽章、規格 chips、已下架標籤。點擊導航至商品詳情頁。

```vue
<!-- web/src/components/DashboardCard.vue -->
<script setup lang="ts">
// props: item, categoryName, isLowest, lowestPrice
// 使用 usePriceDelta 取得 currentPrice / deltaClass / deltaText
// 使用 specChipTexts 取得規格 chips
// 使用 formatPrice 格式化價格
// 點擊 → router.push(`/product/${item.id}`)
</script>

<template>
  <article
    class="dashboard-card"
    tabindex="0"
    role="button"
    :aria-label="cardLabel"
    @click="router.push(`/product/${item.id}`)"
    @keydown="onKeydown"
  >
    <div class="dc-top">
      <div class="dc-name">{{ item.name }}</div>
      <div v-if="item.status === 'gone'" class="dc-gone">已下架</div>
      <span v-else-if="isLowest" class="dc-lowest" title="歷史新低">🥇</span>
    </div>
    <div v-if="specChips.length" class="dc-specs">
      <span v-for="chip in specChips" :key="chip" class="chip">{{ chip }}</span>
    </div>
    <div class="dc-price">
      <template v-if="item.status === 'gone'">
        <span class="dc-current dc-gone-text">已下架</span>
      </template>
      <template v-else>
        <span class="dc-current">{{ currentPrice != null ? formatPrice(currentPrice) : '—' }}</span>
        <span v-if="lowestPrice != null && lowestPrice !== currentPrice" class="dc-history-low">
          歷史最低 {{ formatPrice(lowestPrice) }}
        </span>
      </template>
    </div>
  </article>
</template>
```

**Props 介面**：

```typescript
defineProps<{
  item: Item
  categoryName: string
  isLowest: boolean        // 目前價格 === 該分類歷史最低價
  lowestPrice: number | null  // 該分類歷史最低價（展示用）
}>()
```

### 2.4 DashboardSkeleton 元件

**職責**：全頁骨架屏。Tab 區域（5 個 tab 佔位）+ 列表區域（10 個卡片佔位）。CSS 動畫（shimmer）。資料載入完成後用 CSS transition 淡出。

```vue
<!-- web/src/components/DashboardSkeleton.vue -->
<template>
  <div class="dashboard-skeleton" aria-hidden="true">
    <!-- Tab 區域：5 個 tab 佔位 -->
    <div class="ds-tabs">
      <div v-for="i in 5" :key="i" class="ds-tab shimmer" />
    </div>
    <!-- 列表區域：10 個卡片佔位 -->
    <div class="ds-list">
      <div v-for="i in 10" :key="i" class="ds-card shimmer" />
    </div>
  </div>
</template>
```

**CSS 動畫**：

```css
.shimmer {
  background: linear-gradient(90deg, var(--surface) 25%, var(--surface-2) 50%, var(--surface) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

### 2.5 DashboardView 頁面

**職責**：整合 Tab 列表、useDashboard、DashboardCard 列表、ErrorState、EmptyState、DashboardSkeleton。Tab 切換呼叫 `loadCategory(id)`。

```vue
<!-- web/src/views/DashboardView.vue -->
<script setup lang="ts">
// 匯入
import { computed, watch } from "vue"
import { useItems } from "@/composables/useItems"
import { useDashboard } from "@/composables/useDashboard"
import DashboardCard from "@/components/DashboardCard.vue"
import DashboardSkeleton from "@/components/DashboardSkeleton.vue"
import ErrorState from "@/components/ErrorState.vue"
import EmptyState from "@/components/EmptyState.vue"

const { items, categories, activeCategoryId, loading, error, retry, itemToCategory, loadCategory } = useItems()

// Dashboard 專屬：過濾出目前選中分類的商品（全域 items 已由 useItems 聚合）
const categoryItems = computed(() => {
  const id = activeCategoryId.value
  if (id == null) return []
  return items.value.filter(item => itemToCategory.value.get(item.id) === id)
})

// useDashboard 負責排序 + Top 10 + categoryLowest（Tech Decision D4）
// dashboardItems 已含 isLowest / lowestPrice，無需額外 enriching
const { dashboardItems } = useDashboard(categoryItems, activeCategoryId)

// 預設選取第一個分類（categories 載入後自動選取）
watch(categories, (cats) => {
  if (cats.length > 0 && activeCategoryId.value == null) {
    loadCategory(cats[0].id)
  }
}, { immediate: true })

// Tab 切換
function switchTab(id: string) {
  loadCategory(id)
}
</script>

<template>
  <main class="dashboard-view">
    <!-- 骨架屏 -->
    <DashboardSkeleton v-if="loading && !dashboardItems.length" />

    <!-- 錯誤狀態 -->
    <ErrorState v-else-if="error" :kind="error" @retry="retry" />

    <!-- 正常顯示 -->
    <template v-else>
      <!-- Tab 列表 -->
      <nav class="dashboard-tabs" aria-label="分類切換">
        <button
          v-for="cat in categories"
          :key="cat.id"
          type="button"
          class="tab-btn"
          :class="{ active: activeCategoryId === cat.id }"
          @click="switchTab(cat.id)"
        >
          {{ cat.name }}
          <span class="tab-count">{{ cat.count }}</span>
        </button>
      </nav>

      <!-- 商品列表 -->
      <section v-if="dashboardItems.length" class="dashboard-list">
        <DashboardCard
          v-for="di in dashboardItems"
          :key="di.item.id"
          :item="di.item"
          :category-name="categories.find(c => c.id === activeCategoryId)?.name ?? ''"
          :is-lowest="di.isLowest"
          :lowest-price="di.lowestPrice"
        />
      </section>

      <!-- 空狀態 -->
      <EmptyState v-else kind="category" />
    </template>
  </main>
</template>
```

### 2.6 路由註冊

```typescript
// web/src/router/index.ts — 新增路由（懶載入）
{
  path: "/dashboard",
  name: "dashboard",
  component: () => import("@/views/DashboardView.vue"),
},
```

> Dashboard 為輕量頁面（無 lightweight-charts），懶載入 chunk 預估 <10KB gzipped。

### 2.7 導覽列加入 Dashboard 連結

在 `App.vue` 的 `<header>` 區塊，於 logo 與「我的追蹤」之間新增 Dashboard 連結：

```vue
<router-link to="/dashboard" class="nav-link">
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <rect x="3" y="3" width="7" height="7" />
    <rect x="14" y="3" width="7" height="7" />
    <rect x="14" y="14" width="7" height="7" />
    <rect x="3" y="14" width="7" height="7" />
  </svg>
  Dashboard
</router-link>
```

---

## 3. API 合約

> **不適用**：本功能無後端 API 改動。資料來源為靜態 JSON（`api/items/{g}.json`），由現有 `useItems` singleton 載入。

---

## 4. 資料流

```
使用者進入 /#/dashboard
  │
  ├─ DashboardView 掛載
  │    └─ useItems()（singleton，已有 index + categories + items 資料）
  │         └─ bootstrap() → fetch index.json → categories[] → fetch 第一分類檔
  │
  ├─ watch(categories) → 自動選取第一分類 → loadCategory(first.id)
  │    └─ useItems.loadCategory(id) → fetch api/items/{g}.json（如未載入）
  │
  ├─ useDashboard(categoryItems, activeCategoryId)
  │    ├─ categoryLowest：遍歷全域 items → 每分類歷史最低價 Map（Tech Decision D4）
  │    └─ dashboardItems：過濾分類 → 按 currentPrice 升冪 → slice(0, 10) → 含 isLowest/lowestPrice
  │
  └─ DashboardCard 渲染
       ├─ usePriceDelta(item) → currentPrice / deltaClass / deltaText
       ├─ specChipTexts(spec, categoryName) → 規格 chips
       └─ formatPrice() → 價格字串
```

**同步性質**：所有資料轉換（排序、Top 10、歷史最低價計算）皆為 computed（同步響應式），無額外非同步操作。

---

## 5. 邊界條件處理

| 情境 | 來源 | 處理方式 |
|------|------|---------|
| 商品數少於 10 筆 | BDD @edge-case `#11` | `slice(0, 10)` 自動處理：不足 10 筆顯示全部，不補空位 |
| 價格格式化千分位 | BDD @edge-case `#12` | `formatPrice(15800)` → `"NT$ 15,800"`（已由 `utils/format.ts` 實作） |
| 歷史新低價徽章 | BDD @edge-case `#13` | `useDashboard` 內 `categoryLowest` Map 比對 `item.id === lowest.itemId` → 顯示 🥇 |
| 已下架商品 | BDD @edge-case `#14` | `item.status === 'gone'` → 顯示「已下架」標籤，隱藏目前價格 |
| 多分類同時載入失敗 | BDD @edge-case `#15` | `useItems.error` 聚合判定：任一分類失敗 → ErrorState 顯示 + 重試按鈕 |
| API 載入失敗 | BDD @error-handling `#8` | `error` ref 有值 → `ErrorState` 顯示「無法載入資料」+ [重試] 按鈕 |
| 點擊重試 | BDD @error-handling `#9` | `ErrorState` emit `retry` → `useItems.retry()` → 重新 fetch |
| 分類無商品 | BDD @error-handling `#10` | `dashboardItems.length === 0` → `EmptyState` 顯示「暫無商品資料」 |
| 分類 Tab 預設選取 | BDD @business-rules `#20` | `watch(categories, ...)` 有值時自動選取第一分類（依 `categories` 順序） |
| 歷史最低價計算與 usePriceHistory 一致性 | Tech Decision §7 風險 | 共用同一事實來源（`item.history`）；`useDashboard` 內 `categoryLowest` 取 history 末筆 p，與 `usePriceHistory.stats.low` 邏輯等價 |
| 快速切換 Tab（loadCategory 併發） | Tech Decision §7 風險 | `useItems.loadCategory` 已有快取（`loadedIds`）+ in-flight 去重（`inFlight` Map） |

---

## 6. CSS 關鍵樣式

| class | 樣式重點 |
|-------|---------|
| `.dashboard-view` | 全頁容器，`padding` 與 ListingView 一致 |
| `.dashboard-tabs` | Tab 列表容器，`display: flex; gap` 水平排列，底部 border 分隔 |
| `.tab-btn` | Tab 按鈕，`padding`、`border-radius`、`background: transparent`；`.tab-btn.active` 顯示 `border-bottom: 2px solid var(--brand)` + `color: var(--brand)` |
| `.tab-count` | Tab 內商品數 badge，`font-size: 0.72rem`、`color: var(--text-dim)` |
| `.dashboard-list` | 商品列表容器，`display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap` |
| `.dashboard-card` | 精簡版卡片，與 `.product-card` 類似結構但不含 `.pc-actions`、`.pc-price` 之外的互動元素 |
| `.dc-top` | 卡片頂部，`display: flex; justify-content: space-between` |
| `.dc-name` | 商品名稱，`font-size: 0.95rem; font-weight: 600` |
| `.dc-gone` | 已下架標籤，與 `.product-card .pc-gone` 樣式一致 |
| `.dc-lowest` | 🥇 歷史新低徽章，`font-size: 1.2rem` |
| `.dc-specs` | 規格 chips 容器，`display: flex; flex-wrap: wrap; gap: 4px` |
| `.dc-price` | 價格區塊，`display: flex; align-items: baseline; gap: 8px` |
| `.dc-current` | 目前價格，`font-size: 1.15rem; font-weight: 700` |
| `.dc-history-low` | 歷史最低價文字，`font-size: 0.78rem; color: var(--text-dim)` |
| `.dc-gone-text` | 已下架文字（替代價格），`color: var(--text-dim)` |
| `.dashboard-skeleton` | 骨架屏容器，全頁佔位 |
| `.ds-tabs` | Tab skeleton，`display: flex; gap` |
| `.ds-tab` | Tab 佔位方塊，`width: 80px; height: 32px` |
| `.ds-list` | 列表 skeleton，`display: grid`（與 `.dashboard-list` 同 layout） |
| `.ds-card` | 卡片 skeleton 佔位，`height: 120px; border-radius: var(--radius)` |
| `.shimmer` | 動畫，`background: linear-gradient(90deg, ...); animation: shimmer 1.5s infinite` |

---

## 7. 開發順序

| 步驟 | 內容 | 依賴 |
|------|------|------|
| 1 | `useDashboard` composable：排序 + Top 10 + 歷史最低價計算（含 `extractCurrentPrice`、`DashboardItem` 型別） | — |
| 2 | `useDashboard` 單元測試：排序正確性、Top 10 截斷、null 價格排序、空陣列處理 | #1 |
| 3 | `DashboardCard` 元件：props 介面、usePriceDelta 整合、specChipTexts 整合、🥇 徽章、已下架標籤、點擊導航 | #1 |
| 4 | `DashboardCard` 單元測試：各 props 組合（正常/已下架/歷史新低/空 history） | #3 |
| 5 | `DashboardSkeleton` 元件：Tab 佔位 + 列表佔位 + shimmer 動畫 | — |
| 6 | `DashboardView` 頁面：整合 useItems + useDashboard + DashboardCard + ErrorState + EmptyState + DashboardSkeleton | #1–5 |
| 7 | `DashboardView` 整合測試：Tab 切換、Top 10 排序驗證、歷史最低價顯示、骨架屏→列表轉場、錯誤重試 | #6 |
| 8 | 路由註冊：`/dashboard` → 懶載入 `DashboardView` | #6 |
| 9 | 導覽列加入 Dashboard 連結（App.vue header） | #8 |
| 10 | E2E 測試（Playwright）：完整流程 — 進入 Dashboard → 預設分類 → Tab 切換 → Top 10 排序 → 點擊卡片進詳情 → 錯誤重試 | #8–9 |

---

## 8. 基礎架構設定

> **不適用**：本功能為純前端，無後端 API 改動、無 Nginx/systemd 設定需求。路由使用 `createWebHashHistory`（GitHub Pages SPA），不需要額外伺服器設定。

---

## 附錄：BDD Scenario 覆蓋對照表

| BDD Scenario | 對應章節/元件 | 驗證方式 |
|--------------|-------------|---------|
| `#1` 透過導覽列進入 Dashboard | §2.7 導覽列連結 + §2.6 路由 | E2E：點擊導覽列 → 顯示骨架屏 |
| `#2` 透過直接訪問 URL 進入 Dashboard | §2.6 路由 `/#/dashboard` | E2E：直接訪問 → 顯示骨架屏 |
| `#3` 資料載入成功後顯示分類與商品 | §2.5 DashboardView watch(categories) | E2E：骨架屏淡出 → 顯示 Tab + 列表 |
| `#4` 商品列表按價格低到高排序並顯示前 10 名 | §2.2 useDashboard computed | E2E：驗證排序 + 最多 10 筆 |
| `#5` 商品卡片顯示完整資訊 | §2.3 DashboardCard（名稱/價格/歷史最低價/規格 chips） | E2E：驗證卡片內容 |
| `#6` 點擊商品卡片進入詳情頁 | §2.3 DashboardCard click → router.push | E2E：點擊 → 導航至 /product/:id |
| `#7` 切換分類查看不同分類的商品 | §2.5 DashboardView switchTab | E2E：Tab 切換 → 列表更新 |
| `#8` API 載入失敗顯示錯誤頁面 | §5 邊界條件 + ErrorState | E2E：mock 失敗 → ErrorState 顯示 |
| `#9` 點擊重試按鈕重新載入資料 | §5 邊界條件 + ErrorState retry | E2E：點重試 → 重新載入 |
| `#10` 分類無商品時顯示空狀態 | §5 邊界條件 + EmptyState | E2E：mock 空分類 → EmptyState |
| `#11` 分類商品數少於 10 筆時顯示全部 | §5 邊界條件 `slice(0,10)` | 單元測試：驗證 <10 筆時顯示全部 |
| `#12` 價格格式化顯示千分位 | §2.3 DashboardCard + formatPrice | 單元測試：formatPrice(15800) |
| `#13` 歷史新低價商品顯示徽章 | §2.2 useDashboard `categoryLowest` + DashboardCard | E2E：驗證 🥇 徽章 |
| `#14` 已下架商品顯示下架標籤 | §2.3 DashboardCard `item.status === 'gone'` | 單元測試：status=gone 時顯示標籤 |
| `#15` 多個分類同時載入失敗 | §5 邊界條件 + ErrorState | E2E：mock 多分類失敗 → ErrorState |
| `#16` Dashboard 無需登入即可訪問 | §2.6 路由（無 auth guard） | E2E：無登入狀態可訪問 |
| `#17` 每個分類最多顯示前 10 名 | §2.2 useDashboard slice(0,10) | 單元測試：>10 筆時截斷 |
| `#18` 商品按價格由低到高排序 | §2.2 useDashboard sort | 單元測試：驗證排序正確性 |
| `#19` 預設選取第一個分類 | §2.5 DashboardView watch(categories) | E2E：載入後自動選取第一 Tab |
| `#20` 最便宜商品標示金牌徽章 | §2.3 DashboardCard isLowest | E2E：第一筆顯示 🥇 |
