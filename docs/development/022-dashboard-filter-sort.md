# Dashboard 商品篩選與排序 — 開發規格

> **狀態**：✅ 已完成
> **功能編號**：022 — dashboard-filter-sort
> **Issue**：#22
> **技術棧**：Vue 3.5.13 · Vite 6.0.0 · TypeScript 5.6.3 · Vitest 3.2.4 · Playwright 1.62.1
> **Tech Decision**：`docs/tech-decisions/022-dashboard-filter-sort.md`
> **操作流程**：`docs/interaction-flows/022-dashboard-filter-sort.md`
> **BDD**：`docs/bdds/022-dashboard-filter-sort.feature`
> **測試計畫**：不適用（本功能為純前端，BDD 可直接作為 E2E 測試依據）

---

## 概述

讓 Dashboard 商品列表支援排序（3 種模式）與篩選（價格區間 + 品牌），使用者可組合多個條件快速找到目標商品。核心包含：

1. **useDashboardFilters** — 管理篩選狀態（sortMode / priceMin / priceMax / selectedBrands）與過濾邏輯
2. **useDashboardSort** — 排序 pipeline，接收篩選後商品 + sortMode，回傳排序結果
3. **DashboardFilterBar** — 篩選控制項 UI（排序下拉 + 價格輸入 + 品牌 checkbox）
4. **DashboardView 整合** — 將新 composable + 組件接入現有 Dashboard 流程

---

## 1. 後端實作規格

### 不適用

本功能為純前端 client-side 篩選與排序，不涉及後端 API 變更。

---

## 2. 前端實作規格

### 2.1 檔案改動總覽

```
web/src/
├── composables/
│   ├── useDashboardFilters.ts    ← 新增：篩選狀態管理 + 過濾邏輯
│   └── useDashboardSort.ts       ← 新增：排序 pipeline
├── components/
│   └── DashboardFilterBar.vue    ← 新增：篩選控制項 UI（排序下拉 + 價格輸入 + 品牌 checkbox）
├── views/
│   └── DashboardView.vue         ← 修改：整合 useDashboardFilters + useDashboardSort + DashboardFilterBar
└── types/
    └── dashboardFilter.ts        ← 新增：篩選狀態型別定義
```

### 2.2 types/dashboardFilter.ts — 篩選狀態型別

```typescript
// web/src/types/dashboardFilter.ts — Dashboard 篩選狀態型別（022 Tech Decision D4）

/** 排序模式 */
export type SortMode = "price_asc" | "price_desc" | "recently_updated"

/** 價格區間篩選狀態 */
export interface PriceRange {
  min: number | null  // null = 未設定
  max: number | null  // null = 未設定
}

/** Dashboard 篩選狀態（useDashboardFilters 的 state 介面） */
export interface DashboardFilterState {
  sortMode: SortMode
  priceRange: PriceRange
  selectedBrands: Set<string>  // 已勾選的品牌名稱集合
}

/** 排序選項（供下拉選單使用） */
export interface SortOption {
  value: SortMode
  label: string
}

/** 篩選控制項的 emit events */
export interface DashboardFilterEmits {
  (e: "update:sort", mode: SortMode): void
  (e: "update:price-min", value: number | null): void
  (e: "update:price-max", value: number | null): void
  (e: "update:brands", brands: Set<string>): void
  (e: "clear"): void
}
```

### 2.3 composables/useDashboardFilters.ts — 篩選狀態管理

```typescript
// web/src/composables/useDashboardFilters.ts — Dashboard 篩選邏輯（022 Tech Decision D4）
// 職責：管理 sortMode / priceRange / selectedBrands，提供 filteredItems + clearFilters
// 與 useFilters（keyword + SpecCondition）獨立，不合併（Tech Decision D5）

import { ref, computed, watch, type Ref } from "vue"
import type { Item } from "@/types/item"
import type { SortMode, PriceRange, DashboardFilterState } from "@/types/dashboardFilter"

/** 從 Item 提取目前價格（history 最後一筆 p） */
function extractPrice(item: Item): number | null {
  return item.history.length > 0 ? item.history[item.history.length - 1].p : null
}

/** 從 Item 提取品牌（spec.brand） */
function extractBrand(item: Item): string | null {
  return typeof item.spec.brand === "string" ? item.spec.brand : null
}

/**
 * Dashboard 篩選 composable
 * @param items — 已按分類過濾的商品列表（Ref）
 */
export function useDashboardFilters(items: Ref<Item[]>) {
  // ── State ──
  const sortMode = ref<SortMode>("price_asc")
  const priceMin = ref<number | null>(null)
  const priceMax = ref<number | null>(null)
  const selectedBrands = ref<Set<string>>(new Set())

  // ── Auto-swap price min/max（BDD @edge-case） ──
  watch([priceMin, priceMax], ([min, max]) => {
    if (min != null && max != null && min > max) {
      priceMin.value = max
      priceMax.value = min
    }
  })

  // ── 可用品牌列表（從目前分類商品中提取唯一品牌） ──
  const availableBrands = computed<string[]>(() => {
    const brands = new Set<string>()
    for (const item of items.value) {
      const b = extractBrand(item)
      if (b) brands.add(b)
    }
    return [...brands].sort()
  })

  // ── 篩選管線 ──
  const filteredItems = computed<Item[]>(() => {
    let result = items.value

    // 價格下限
    if (priceMin.value != null) {
      result = result.filter((item) => {
        const price = extractPrice(item)
        return price != null && price >= priceMin.value!
      })
    }

    // 價格上限
    if (priceMax.value != null) {
      result = result.filter((item) => {
        const price = extractPrice(item)
        return price != null && price <= priceMax.value!
      })
    }

    // 品牌篩選（多品牌取聯集：勾選 A 或 B 的商品皆顯示）
    if (selectedBrands.value.size > 0) {
      result = result.filter((item) => {
        const brand = extractBrand(item)
        return brand != null && selectedBrands.value.has(brand)
      })
    }

    return result
  })

  // ── 排序管線（在篩選之後執行） ──
  const sortedItems = computed<Item[]>(() => {
    const arr = [...filteredItems.value]
    switch (sortMode.value) {
      case "price_asc":
        return arr.sort((a, b) => {
          const pa = extractPrice(a)
          const pb = extractPrice(b)
          if (pa == null) return 1
          if (pb == null) return -1
          return pa - pb
        })
      case "price_desc":
        return arr.sort((a, b) => {
          const pa = extractPrice(a)
          const pb = extractPrice(b)
          if (pa == null) return 1
          if (pb == null) return -1
          return pb - pa
        })
      case "recently_updated":
        return arr.sort((a, b) => {
          // last_seen 日期由新到舊
          return b.last_seen.localeCompare(a.last_seen)
        })
      default:
        return arr
    }
  })

  // ── 是否有 active 篩選（供清除按鈕顯示判斷） ──
  const hasActiveFilter = computed(() => {
    return (
      priceMin.value != null ||
      priceMax.value != null ||
      selectedBrands.value.size > 0
    )
  })

  // ── 操作方法 ──
  function setSortMode(mode: SortMode) { sortMode.value = mode }
  function setPriceMin(v: number | null) { priceMin.value = v }
  function setPriceMax(v: number | null) { priceMax.value = v }

  function toggleBrand(brand: string) {
    const next = new Set(selectedBrands.value)
    if (next.has(brand)) {
      next.delete(brand)
    } else {
      next.add(brand)
    }
    selectedBrands.value = next
  }

  /** 清除所有篩選（保留 sortMode — Tech Decision D7） */
  function clearFilters() {
    priceMin.value = null
    priceMax.value = null
    selectedBrands.value = new Set()
  }

  /** 重設全部（含 sortMode） */
  function resetAll() {
    clearFilters()
    sortMode.value = "price_asc"
  }

  return {
    // State
    sortMode,
    priceMin,
    priceMax,
    selectedBrands,
    // Computed
    availableBrands,
    filteredItems,
    sortedItems,
    hasActiveFilter,
    // Methods
    setSortMode,
    setPriceMin,
    setPriceMax,
    toggleBrand,
    clearFilters,
    resetAll,
  }
}
```

### 2.4 composables/useDashboardSort.ts — 排序 pipeline（可選輔助）

> **說明**：排序邏輯已內含在 useDashboardFilters.sortedItems 中。此檔案為**可選的獨立抽取**，若團隊偏好更細粒度的分離可使用；否則可省略，直接使用 useDashboardFilters 的 sortedItems。

```typescript
// web/src/composables/useDashboardSort.ts — 獨立排序 composable（022 Tech Decision D1，可選）
// 若排序邏輯需獨立測試或跨 composable 共用時使用

import { computed, type Ref } from "vue"
import type { Item } from "@/types/item"
import type { SortMode } from "@/types/dashboardFilter"

function extractPrice(item: Item): number | null {
  return item.history.length > 0 ? item.history[item.history.length - 1].p : null
}

/**
 * 排序 composable
 * @param items — 已篩選的商品列表
 * @param sortMode — 目前排序模式
 */
export function useDashboardSort(
  items: Ref<Item[]>,
  sortMode: Ref<SortMode>,
) {
  const sortedItems = computed<Item[]>(() => {
    const arr = [...items.value]
    switch (sortMode.value) {
      case "price_asc":
        return arr.sort((a, b) => {
          const pa = extractPrice(a)
          const pb = extractPrice(b)
          if (pa == null) return 1
          if (pb == null) return -1
          return pa - pb
        })
      case "price_desc":
        return arr.sort((a, b) => {
          const pa = extractPrice(a)
          const pb = extractPrice(b)
          if (pa == null) return 1
          if (pb == null) return -1
          return pb - pa
        })
      case "recently_updated":
        return arr.sort((a, b) => b.last_seen.localeCompare(a.last_seen))
      default:
        return arr
    }
  })

  return { sortedItems }
}
```

### 2.5 components/DashboardFilterBar.vue — 篩選控制項 UI

```vue
<!-- web/src/components/DashboardFilterBar.vue — 排序/篩選控制列（022 Tech Decision D2/D3） -->
<!-- 包含：排序下拉選單 + 價格區間輸入 + 品牌 Checkbox + 清除按鈕 + 商品數量 -->
<script setup lang="ts">
import { computed } from "vue"
import type { SortMode, SortOption } from "@/types/dashboardFilter"

const props = defineProps<{
  sortMode: SortMode
  priceMin: number | null
  priceMax: number | null
  availableBrands: string[]
  selectedBrands: Set<string>
  resultCount: number
  totalCount: number
  hasActiveFilter: boolean
}>()

const emit = defineEmits<{
  (e: "update:sort", mode: SortMode): void
  (e: "update:price-min", value: number | null): void
  (e: "update:price-max", value: number | null): void
  (e: "update:brands", brand: string): void
  (e: "clear"): void
}>()

const sortOptions: SortOption[] = [
  { value: "price_asc", label: "價格低→高" },
  { value: "price_desc", label: "價格高→低" },
  { value: "recently_updated", label: "最近更新" },
]

const countLabel = computed(() => {
  return `顯示 ${props.resultCount} / ${props.totalCount} 件商品`
})

function onPriceMinInput(e: Event) {
  const v = (e.target as HTMLInputElement).value
  emit("update:price-min", v === "" ? null : Number(v))
}

function onPriceMaxInput(e: Event) {
  const v = (e.target as HTMLInputElement).value
  emit("update:price-max", v === "" ? null : Number(v))
}
</script>

<template>
  <div class="filter-bar" role="search" aria-label="商品篩選與排序">
    <!-- 排序下拉 -->
    <div class="filter-bar__sort">
      <label for="sort-select" class="filter-label">排序</label>
      <select
        id="sort-select"
        class="sort-select"
        :value="sortMode"
        @change="emit('update:sort', ($event.target as HTMLSelectElement).value as SortMode)"
      >
        <option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </option>
      </select>
    </div>

    <!-- 價格區間 -->
    <div class="filter-bar__price">
      <span class="filter-label">價格</span>
      <input
        type="number"
        class="price-input"
        placeholder="下限"
        :value="priceMin ?? ''"
        min="0"
        aria-label="價格下限"
        @input="onPriceMinInput"
      />
      <span class="price-separator">–</span>
      <input
        type="number"
        class="price-input"
        placeholder="上限"
        :value="priceMax ?? ''"
        min="0"
        aria-label="價格上限"
        @input="onPriceMaxInput"
      />
    </div>

    <!-- 品牌 Checkbox -->
    <div v-if="availableBrands.length > 0" class="filter-bar__brands">
      <span class="filter-label">品牌</span>
      <div class="brand-list" role="group" aria-label="品牌篩選">
        <label
          v-for="brand in availableBrands"
          :key="brand"
          class="brand-checkbox"
        >
          <input
            type="checkbox"
            :checked="selectedBrands.has(brand)"
            @change="emit('update:brands', brand)"
          />
          <span class="brand-checkbox__label">{{ brand }}</span>
        </label>
      </div>
    </div>

    <!-- 數量 + 清除 -->
    <div class="filter-bar__footer">
      <span class="result-count">{{ countLabel }}</span>
      <button
        v-if="hasActiveFilter"
        type="button"
        class="clear-btn"
        @click="emit('clear')"
      >
        清除篩選
      </button>
    </div>
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}

.filter-bar__sort,
.filter-bar__price,
.filter-bar__brands {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-dim);
  min-width: 36px;
}

/* Sort Select */
.sort-select {
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text);
  font-size: 0.85rem;
  cursor: pointer;
}

/* Price Inputs */
.price-input {
  width: 100px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text);
  font-size: 0.85rem;
  font-variant-numeric: tabular-nums;
}

.price-input:focus {
  border-color: var(--brand);
  outline: none;
}

.price-separator {
  color: var(--text-dim);
}

/* Brand Checkbox List */
.brand-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  max-height: 80px;
  overflow-y: auto;
}

.brand-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.82rem;
  cursor: pointer;
}

.brand-checkbox__label {
  color: var(--text);
}

/* Footer */
.filter-bar__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.result-count {
  font-size: 0.82rem;
  color: var(--text-dim);
}

.clear-btn {
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--brand);
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}

.clear-btn:hover {
  background: var(--brand-soft);
}

/* RWD */
@media (max-width: 768px) {
  .price-input {
    width: 80px;
  }
}

@media (max-width: 639px) {
  .filter-bar__sort,
  .filter-bar__price {
    flex-wrap: wrap;
  }
  .price-input {
    width: 70px;
  }
}
</style>
```

### 2.6 views/DashboardView.vue — 整合改動

```vue
<!-- web/src/views/DashboardView.vue — 022 整合變更摘要 -->
<!-- 新增 import + 使用 useDashboardFilters + 插入 DashboardFilterBar -->

<script setup lang="ts">
import { computed, watch } from "vue"
import { useItems } from "@/composables/useItems"
import { useDashboard } from "@/composables/useDashboard"
import { useSpecGroups } from "@/composables/useSpecGroups"
import { useDashboardFilters } from "@/composables/useDashboardFilters"  // ← 新增
import CategoryTabs from "@/components/CategoryTabs.vue"
import SpecGroupChips from "@/components/SpecGroupChips.vue"
import DashboardCard from "@/components/DashboardCard.vue"
import DashboardFilterBar from "@/components/DashboardFilterBar.vue"  // ← 新增
import DashboardSkeleton from "@/components/DashboardSkeleton.vue"
import ErrorState from "@/components/ErrorState.vue"
import EmptyState from "@/components/EmptyState.vue"

const {
  items, categories, activeCategoryId, loading, error, retry,
  itemToCategory, loadCategory, isLoadingCategory,
} = useItems()

// —— 分類過濾（同現有） ——
const categoryItems = computed(() => {
  const id = activeCategoryId.value
  if (id == null) return []
  return items.value.filter((item) => itemToCategory.value.get(item.id) === id)
})

// —— 分組（018，同現有） ——
const categoryName = computed(() => {
  const id = activeCategoryId.value
  return id ? categories.value.find((c) => c.id === id)?.name ?? null : null
})
const specGroups = useSpecGroups(categoryItems, categoryName)

// —— Dashboard 展示邏輯（017，同現有） ——
const { activeCategory, switchCategory } = useDashboard(
  categoryItems,
  activeCategoryId,
  specGroups.resetGroup,
)

// —— 022 新增：篩選與排序 ——
const {
  sortMode, priceMin, priceMax, selectedBrands,
  availableBrands, filteredItems, sortedItems, hasActiveFilter,
  setSortMode, setPriceMin, setPriceMax, toggleBrand, clearFilters,
} = useDashboardFilters(categoryItems)

// —— 022 整合：最終顯示列表（分組 > 篩選 > 排序） ——
// 使用 specGroups.groupedItems 作為基礎（已含分組篩選 + 預設排序）
// 再套用 useDashboardFilters 的篩選 + 排序
const displayItems = computed(() => {
  // 先取分組後的商品（已含分組篩選）
  const base = specGroups.groupedItems.value
  // 再套用 022 篩選 + 排序
  // 注意：useDashboardFilters 接收的是 categoryItems，但此處需要的是分組後的商品
  // 因此改為：先篩選分組商品，再排序
  // → 需要將 filteredItems 改為接收任意 items，或在此處直接處理
  // 實際做法：useDashboardFilters 內部的 filteredItems 已基於 categoryItems 計算
  // 此處改為使用 sortedItems（已含篩選+排序），但需確保與分組的交集
  // 最終方案：以 sortedItems 為主，但限制在分組範圍內
  const groupedIds = new Set(base.map(i => i.id))
  return sortedItems.value.filter(i => groupedIds.has(i.id))
})

// —— loadingIds（同現有） ——
const loadingIds = computed(() => {
  const s = new Set<string>()
  const id = activeCategoryId.value
  if (id && isLoadingCategory(id)) s.add(id)
  return s
})

// —— 預設選取第一個分類（同現有） ——
watch(
  categories,
  (cats) => {
    if (cats.length > 0 && activeCategoryId.value == null) {
      loadCategory(cats[0].id)
    }
  },
  { immediate: true },
)
</script>

<template>
  <main class="dashboard-view">
    <DashboardSkeleton v-if="loading && !dashboardItems?.length" />
    <ErrorState v-else-if="error" :kind="error" @retry="retry" />

    <template v-else>
      <CategoryTabs
        v-if="categories.length > 0"
        :categories="categories"
        :active-id="activeCategoryId"
        :loading-ids="loadingIds"
        @select="switchCategory"
      />

      <SpecGroupChips
        v-if="specGroups.hasGroups.value"
        :groups="specGroups.groups.value"
        :selected-key="specGroups.selectedGroupKey.value"
        @select="specGroups.selectGroup"
      />

      <!-- 022 新增：篩選控制列（僅在有商品時顯示） -->
      <DashboardFilterBar
        v-if="categoryItems.length > 0"
        :sort-mode="sortMode"
        :price-min="priceMin"
        :price-max="priceMax"
        :available-brands="availableBrands"
        :selected-brands="selectedBrands"
        :result-count="displayItems.length"
        :total-count="categoryItems.length"
        :has-active-filter="hasActiveFilter"
        @update:sort="setSortMode"
        @update:price-min="setPriceMin"
        @update:price-max="setPriceMax"
        @update:brands="toggleBrand"
        @clear="clearFilters"
      />

      <section v-if="displayItems.length" class="dashboard-list" aria-label="商品列表">
        <DashboardCard
          v-for="di in displayItems"
          :key="di.id"
          :item="di"
          :category-name="activeCategory?.name ?? ''"
          :is-lowest="false"
          :lowest-price="null"
        />
      </section>

      <!-- 022 新增：篩選空狀態 -->
      <EmptyState
        v-else-if="hasActiveFilter"
        kind="filter"
        @clear="clearFilters"
      />
      <EmptyState v-else kind="category" />
    </template>
  </main>
</template>
```

> ⚠️ **整合注意事項**：
> - `displayItems` 需要同時考慮分組（specGroups）和篩選排序（useDashboardFilters）
> - 建議在整合時先確認 specGroups.groupedItems 的排序是否會與 useDashboardFilters 的 sortMode 衝突
> - 若衝突，以 useDashboardFilters 的 sortMode 為最終排序依據

---

## 3. API 合約

### 不適用

本功能為純前端 client-side 篩選與排序，不涉及後端 API。

---

## 4. 資料流

```
useItems()                    ← API 載入原始 items + categories
  │
  ▼
categoryItems (computed)      ← 按 activeCategoryId 過濾
  │
  ├──→ useSpecGroups()        ← 分組篩選 → groupedItems
  │         │
  │         ▼
  │    displayItems (computed) ← groupedItems ∩ sortedItems（取交集）
  │
  └──→ useDashboardFilters()  ← 價格/品牌篩選 → filteredItems → 排序 → sortedItems
            │
            ▼
       DashboardFilterBar.vue ← 顯示控制項 + emit events
            │
            ▼
       DashboardView.vue      ← 整合：displayItems → DashboardCard 列表
```

**流程說明**：
1. `useItems()` 載入原始資料（API call， lazy 快取）
2. `categoryItems` 按目前選中分類過濾（computed，同步）
3. `useSpecGroups(categoryItems)` 產生分組後商品（含分組篩選）
4. `useDashboardFilters(categoryItems)` 產生篩選+排序後商品
5. `displayItems` 取兩者的交集（分組 ∩ 篩選排序），確保分組 Chips 與篩選控制項協同運作
6. `DashboardFilterBar` 接收 computed 狀態 + emit 使用者操作事件
7. `DashboardCard` 渲染最終商品列表

**同步/非同步性質**：
- 所有篩選/排序運算為 **computed（同步）**，無需 debounce
- 唯一非同步為 `useItems().loadCategory()`（API call），由 CategoryTabs 觸發

---

## 5. 生命週期

不適用（無 WebSocket、無連線管理、無狀態機）。

---

## 6. 邊界條件處理

| 情境 | 來源 | 處理方式 |
|------|------|---------|
| 價格下限 > 上限 | BDD @edge-case @filter-price | watch 自動交換（priceMin ↔ priceMax） |
| 價格輸入非數字 | BDD @edge-case @filter-price | 空字串 → null，非數字忽略不更新 state |
| 篩選結果為 0 | BDD @error-handling @empty-state | 顯示 EmptyState kind="filter" + 清除按鈕 |
| 品牌篩選無結果 | BDD @error-handling @empty-state | 同上 |
| 該分類無商品 | BDD @edge-case @no-items | 隱藏所有篩選控制項（v-if="categoryItems.length > 0"） |
| 商品無價格（history 為空） | 現有 useDashboard 邏輯 | extractPrice 回傳 null，排序時置底 |
| 商品無品牌（spec.brand 為 undefined） | 現有 ItemSpec 類型 | extractBrand 回傳 null，不出現在品牌列表中 |
| 分組篩選 + 品牌篩選衝突 | 整合場景 | displayItems 取交集，兩者皆需符合 |
| 品牌列表過多（>10 個） | UX 邊界 | brand-list 設 max-height: 80px + overflow-y: auto |
| 所有篩選清除後恢復 | BDD @clear-filters | clearFilters 清除 priceMin/priceMax/selectedBrands，保留 sortMode |

---

## 7. CSS 關鍵樣式

| class | 樣式重點 |
|-------|---------|
| `.filter-bar` | flex-column, gap 12px, border-bottom 分隔 |
| `.sort-select` | padding 6px 12px, border-radius 6px, cursor pointer |
| `.price-input` | width 100px, font-variant-numeric: tabular-nums（數字對齊） |
| `.price-input:focus` | border-color: var(--brand) |
| `.brand-list` | flex-wrap, max-height 80px, overflow-y auto（可捲動） |
| `.brand-checkbox` | inline-flex, gap 4px, cursor pointer |
| `.clear-btn` | border 1px, color var(--brand), hover background var(--brand-soft) |
| `.result-count` | font-size 0.82rem, color var(--text-dim) |

CSS class 名稱須與 DashboardFilterBar.vue 的 template class binding 一致。

---

## 8. 開發順序

| 步驟 | 內容 | 依賴 |
|------|------|------|
| 1 | 新增 `types/dashboardFilter.ts`（型別定義） | - |
| 2 | 新增 `composables/useDashboardFilters.ts`（篩選 + 排序邏輯） | #1 |
| 3 | 新增 `components/DashboardFilterBar.vue`（UI 組件） | #1 |
| 4 | 為 useDashboardFilters 撰寫 unit test（Vitest） | #2 |
| 5 | 修改 `views/DashboardView.vue`（整合新 composable + 組件） | #2, #3 |
| 6 | 為 DashboardFilterBar 撰寫 unit test（Vitest + vue-test-utils） | #3 |
| 7 | E2E 驗證：排序切換、價格篩選、品牌篩選、交集、空狀態、清除 | #5 |
| 8 | RWD 驗證：mobile / tablet 斷點下的篩選控制項顯示 | #5 |

> **DAG 依賴**：#1 → #2 → #4 → #5 → #7；#1 → #3 → #6 → #5；#5 → #8
> 後端：不適用。全部為前端 task。

---

## 附錄：BDD Scenario 對照表

| BDD Scenario | 對應規格章節 | 實作位置 |
|-------------|-------------|---------|
| 預設排序為價格由低到高 | §2.3 sortedItems (price_asc) | useDashboardFilters.ts |
| 切換排序為價格由高到低 | §2.3 sortedItems (price_desc) | useDashboardFilters.ts |
| 切換排序為最近更新 | §2.3 sortedItems (recently_updated) | useDashboardFilters.ts |
| 輸入價格下限篩選 | §2.3 filteredItems (priceMin) | useDashboardFilters.ts |
| 輸入價格上限篩選 | §2.3 filteredItems (priceMax) | useDashboardFilters.ts |
| 同時輸入價格上下限 | §2.3 filteredItems (priceMin + priceMax) | useDashboardFilters.ts |
| 價格下限大於上限自動交換 | §2.3 watch [priceMin, priceMax] | useDashboardFilters.ts |
| 價格輸入非數字時忽略 | §2.5 onPriceMinInput / onPriceMaxInput | DashboardFilterBar.vue |
| 勾選單一品牌篩選 | §2.3 filteredItems (selectedBrands) | useDashboardFilters.ts |
| 勾選多個品牌篩選 | §2.3 filteredItems (selectedBrands.size > 0) | useDashboardFilters.ts |
| 取消勾選品牌 | §2.3 toggleBrand | useDashboardFilters.ts |
| 排序 + 價格篩選交集 | §2.3 sortedItems (after filter) | useDashboardFilters.ts |
| 價格篩選 + 品牌篩選交集 | §2.3 filteredItems (all conditions) | useDashboardFilters.ts |
| 三重篩選交集 | §2.3 filtered + sorted | useDashboardFilters.ts |
| 篩選無結果時顯示空狀態 | §2.6 template v-else-if="hasActiveFilter" | DashboardView.vue |
| 品牌篩選無結果時顯示空狀態 | 同上 | DashboardView.vue |
| 點擊清除篩選重置所有條件 | §2.3 clearFilters | useDashboardFilters.ts |
| 篩選無結果時清除篩選恢復列表 | 同上 + @clear emit | DashboardFilterBar.vue |
| 顯示符合篩選的商品數量 | §2.5 countLabel | DashboardFilterBar.vue |
| 篩選前顯示總數量 | §2.5 totalCount prop | DashboardFilterBar.vue |
| 該分類無商品時不顯示篩選控制項 | §2.6 v-if="categoryItems.length > 0" | DashboardView.vue |
