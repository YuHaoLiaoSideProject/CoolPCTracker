# Dashboard Categories — 開發規格

> **技術棧**：Vue 3.5.13 · TypeScript 5.6.3 · Vite 6.0.0 · Vitest 3.2.4 · Playwright 1.62.1（無後端、無 Pinia）
> **Tech Decision**：`docs/tech-decisions/019-dashboard-categories.md`
> **操作流程**：`docs/interaction-flows/019-dashboard-categories.md`
> **BDD**：`docs/bdds/019-dashboard-categories.feature`
> **測試計畫**：`docs/test-plans/019-dashboard-categories測試計畫.md`
> **狀態**：設計完成，待開發

---

## 概述

在 Dashboard（017 + 018）基礎上增加「分類 Tab 切換」UX 增強：頂部顯示可折疊分類 Tab 列表（>5 個時折疊為「更多 ▼」）、切換時載入 spinner（僅首次載入時顯示）、切換後自動重置規格分組 Chips。核心包含：

1. **`CategoryTabs.vue` 元件**：分類 Tab 列表（折疊 >5 + spinner + active 高亮），可跨頁複用
2. **`useDashboard` 擴充**：新增 `activeCategory` computed + `categoryLoading` computed + `switchCategory` 操作
3. **`useSpecGroups` 微調**：確認暴露 `resetGroup()`（018 已設計，確認實作時可用）
4. **`DashboardView` 擴充**：整合 CategoryTabs + useDashboard.switchCategory

> ⚠️ **依賴**：本功能建立在 017（DashboardView + useDashboard）+ 018（useSpecGroups + SpecGroupChips）基礎上。若 017/018 尚未實作，需先完成其開發順序（見 §8）。

---

## 1. 後端實作規格

> **不適用**：本功能為純前端（Tab 切換 + useItems + useDashboard 整合），無任何後端 API 改動。資料來源為靜態 JSON（`api/items/{g}.json`），由現有 `useItems` singleton 載入。

---

## 2. 前端實作規格

### 2.1 檔案改動總覽

```
web/src/
├── components/
│   └── CategoryTabs.vue              ← 新增：分類 Tab 列表（折疊 >5 + spinner + active 高亮）
├── components/__tests__/
│   └── CategoryTabs.test.ts          ← 新增：CategoryTabs 單元測試
├── composables/
│   ├── useDashboard.ts               ← 修改：新增 activeCategory + categoryLoading + switchCategory
│   ├── useSpecGroups.ts              ← 修改：確認暴露 resetGroup()（018 已設計）
│   └── __tests__/
│       └── useDashboard.test.ts      ← 修改：新增 switchCategory / activeCategory / categoryLoading 測試
└── views/
    └── DashboardView.vue             ← 修改：整合 CategoryTabs + useDashboard.switchCategory
```

### 2.2 `CategoryTabs.vue` — 分類 Tab 列表元件

**職責**：頂部水平分類 Tab 列表。接收分類目錄、目前選中 ID、載入中 ID Set；emit 選取事件。折疊邏輯（>5 → 「更多 ▼」）封裝在元件內部。

#### 2.2.1 Props / Emits

```vue
<!-- web/src/components/CategoryTabs.vue -->
<script setup lang="ts">
import { ref, computed } from "vue"
import type { CategoryMeta } from "@/types/item"

const COLLAPSE_THRESHOLD = 5 // 超過此數量時折疊（BDD @edge-case）

const props = defineProps<{
  categories: CategoryMeta[]    // useItems().categories（index.json 動態提供）
  activeId: string | null       // 目前選中分類 id（null 表示尚未選取）
  loadingIds: Set<string>       // 正在載入的分類 id（spinner 顯示用）
}>()

const emit = defineEmits<{
  (e: "select", id: string): void  // 點擊 Tab → 呼叫 switchCategory
}>()

const isExpanded = ref(false)

/** 是否需要折疊（categories 數量 > COLLAPSE_THRESHOLD） */
const needsCollapse = computed(() => props.categories.length > COLLAPSE_THRESHOLD)

/** 顯示的 categories（折疊模式只顯示前 threshold 個 + 「更多」按鈕在末尾） */
const visibleCategories = computed(() => {
  if (!needsCollapse.value || isExpanded.value) return props.categories
  return props.categories.slice(0, COLLAPSE_THRESHOLD) // 前 5 個（與 BDD / Tech Decision D4 一致）
})

/** 折疊按鈕文字 */
const collapseLabel = computed(() => {
  return isExpanded.value ? "收起 ▲" : "更多 ▼"
})

function toggleExpand(): void {
  isExpanded.value = !isExpanded.value
}

function handleSelect(id: string): void {
  emit("select", id)
}
</script>
```

#### 2.2.2 Template 結構

```vue
<template>
  <nav class="category-tabs" aria-label="分類切換">
    <button
      v-for="cat in visibleCategories"
      :key="cat.id"
      type="button"
      class="cat-tab"
      :class="{
        'cat-tab--active': activeId === cat.id,
        'cat-tab--loading': loadingIds.has(cat.id),
      }"
      :aria-pressed="activeId === cat.id"
      :aria-busy="loadingIds.has(cat.id)"
      @click="handleSelect(cat.id)"
    >
      <span class="cat-tab__name">{{ cat.name }}</span>
      <span v-if="loadingIds.has(cat.id)" class="cat-tab__spinner" aria-hidden="true" />
    </button>

    <!-- 折疊/展開按鈕（categories > 5 時顯示） -->
    <button
      v-if="needsCollapse"
      type="button"
      class="cat-tab cat-tab--toggle"
      @click="toggleExpand"
    >
      {{ collapseLabel }}
    </button>
  </nav>
</template>
```

#### 2.2.3 關鍵行為

| 行為 | 說明 |
|------|------|
| 折疊門檻 | `categories.length > 5` → 顯示前 5 個 Tab + 「更多 ▼」按鈕（BDD @edge-case，Tech Decision D4） |
| 展開 | 顯示全部 Tab + 「收起 ▲」按鈕 |
| 選取高亮 | `activeId === cat.id` 時加 `--active` modifier（反白高亮） |
| Spinner | `loadingIds.has(cat.id)` 時顯示 spinner icon（`--loading` modifier） |
| 橫向捲動 | 手機/小螢幕（≤768px）時 Tab 列表可水平捲動（`overflow-x: auto`） |

#### 2.2.4 `loadingIds` 構建方式（DashboardView 整合時）

```typescript
// DashboardView.vue 中構建 loadingIds
import { computed } from "vue"
import { useItems } from "@/composables/useItems"

const { activeCategoryId, isLoadingCategory } = useItems()

// loadingIds：目前選中分類正在載入時加入 Set
const loadingIds = computed(() => {
  const id = activeCategoryId.value
  const s = new Set<string>()
  if (id && isLoadingCategory(id)) s.add(id)
  return s
})
```

> **設計備註**：`loadingIds` 為 `computed`，僅在 `isLoadingCategory(activeCategoryId)` 為 true 時包含該 ID。快取命中（`loadedIds.has(id)`）→ `loadCategory` 立即返回 → `isLoadingCategory` 不為 true → loadingIds 為空 Set → 無 spinner（Tech Decision D3）。

### 2.3 `useDashboard.ts` 擴充

**職責**：在 017 的 `useDashboard` 基礎上新增：
- `activeCategory: computed<CategoryMeta | null>`（目前分類資訊，供 CategoryTabs 高亮用）
- `categoryLoading: computed<boolean>`（分類級載入中判定，Spinner 顯示用）
- `switchCategory(id: string): Promise<void>`（切換分類 + 重置分組）

```typescript
// web/src/composablesuseDashboard.ts（在 017 基礎上新增）
import { computed, type Ref } from "vue"
import type { Item, CategoryMeta } from "@/types/item"
import { useItems } from "@/composables/useItems"

/** DashboardItem 型別（017 已定義，此處沿用） */
export interface DashboardItem {
  item: Item
  currentPrice: number | null
  isLowest: boolean
  lowestPrice: number | null
}

/**
 * Dashboard 展示邏輯 composable（017 + 019 擴充）
 * @param items            — 已過濾的目前分類商品（由 DashboardView 用 itemToCategory 過濾）
 * @param categoryId       — 目前選中分類 id
 * @param resetGroup       — 重置分組的回呼（由 useSpecGroups.resetGroup 傳入）
 */
export function useDashboard(
  items: Ref<Item[]>,
  categoryId: Ref<string | null>,
  resetGroup?: () => void,
) {
  const itemsState = useItems() // singleton

  // —— 017 已有 ——
  // dashboardItems: computed<DashboardItem[]>（排序 + Top 10 + isLowest/lowestPrice）
  // categoryLowest: computed<Map<string, { price, itemId }>>
  // extractCurrentPrice: (item: Item) => number | null

  // —— 019 新增 ——

  /** 目前分類資訊（供 CategoryTabs 高亮用） */
  const activeCategory = computed<CategoryMeta | null>(() => {
    const id = categoryId.value
    return id ? itemsState.categories.value.find(c => c.id === id) ?? null : null
  })

  /** 分類級載入中判定（Spinner 顯示用） */
  const categoryLoading = computed<boolean>(() => {
    const id = categoryId.value
    return id ? itemsState.isLoadingCategory(id) : false
  })

  /** 切換分類（含分組重置） */
  async function switchCategory(newId: string): Promise<void> {
    // 1. 切換 useItems 的 activeCategoryId + loadCategory
    //    useItems 快取語意：已載入 → 立即切換（無 fetch）；未載入 → fetch 後 append
    await itemsState.loadCategory(newId)
    // 2. 重置 useSpecGroups 的分組狀態（Tech Decision D5）
    resetGroup?.()
  }

  return {
    // 017 已有（沿用）
    // dashboardItems, categoryLowest, extractCurrentPrice
    // 019 新增
    activeCategory,
    categoryLoading,
    switchCategory,
  }
}
```

> **設計備註**：
> - `switchCategory` 不做 AbortController 取消（Tech Decision D1：useItems 快取語意天然處理「僅顯示最新分類」）
> - `resetGroup` 為可選參數（017 的 useDashboard 可能尚未整合 018，傳入時才重置）
> - `activeCategory` 為 computed，從 `useItems().categories` 查詢 `activeCategoryId`

### 2.4 `useSpecGroups.ts` 微調

**職責**：確認暴露 `resetGroup()` 方法（018 已設計，此處確認實作時可用）。

```typescript
// web/src/composables/useSpecGroups.ts — 確認以下方法已暴露

/** 回到「全部」分組 */
function resetGroup(): void {
  selectedGroupKey.value = ALL_GROUP_KEY
}

// return 中確保包含 resetGroup
return {
  groups,
  hasGroups,
  selectedGroupKey,
  groupedItems,
  selectGroup,
  resetGroup, // ← 確認此方法在 return 中
}
```

> 若 018 尚未實作 `resetGroup()`（可能僅在內部使用），此步驟補上暴露即可。

### 2.5 `DashboardView.vue` 擴充

**職責**：整合 CategoryTabs + useDashboard.switchCategory + useSpecGroups.resetGroup。

```vue
<!-- web/src/views/DashboardView.vue（017 + 018 基礎上擴充） -->
<script setup lang="ts">
import { computed, watch } from "vue"
import { useItems } from "@/composables/useItems"
import { useDashboard } from "@/composables/useDashboard"
import { useSpecGroups } from "@/composables/useSpecGroups"
import CategoryTabs from "@/components/CategoryTabs.vue"
import SpecGroupChips from "@/components/SpecGroupChips.vue"
import DashboardCard from "@/components/DashboardCard.vue"
import DashboardSkeleton from "@/components/DashboardSkeleton.vue"
import ErrorState from "@/components/ErrorState.vue"
import EmptyState from "@/components/EmptyState.vue"

const {
  items, categories, activeCategoryId, loading, error, retry,
  itemToCategory, loadCategory, isLoadingCategory,
} = useItems()

// —— 分類過濾 ——
const categoryItems = computed(() => {
  const id = activeCategoryId.value
  if (id == null) return []
  return items.value.filter(item => itemToCategory.value.get(item.id) === id)
})

// —— 分組（018）——
const categoryName = computed(() => {
  const id = activeCategoryId.value
  return id ? categories.value.find(c => c.id === id)?.name ?? null : null
})
const specGroups = useSpecGroups(categoryItems, categoryName)

// —— Dashboard 邏輯（017 + 019）——
const { dashboardItems, activeCategory, categoryLoading, switchCategory } =
  useDashboard(categoryItems, activeCategoryId, specGroups.resetGroup)

// —— loadingIds（CategoryTabs spinner 用）——
const loadingIds = computed(() => {
  const s = new Set<string>()
  const id = activeCategoryId.value
  if (id && isLoadingCategory(id)) s.add(id)
  return s
})

// —— 預設選取第一個分類（017 已有）——
watch(categories, (cats) => {
  if (cats.length > 0 && activeCategoryId.value == null) {
    loadCategory(cats[0].id)
  }
}, { immediate: true })
</script>

<template>
  <main class="dashboard-view">
    <!-- 骨架屏 -->
    <DashboardSkeleton v-if="loading && !dashboardItems.length" />

    <!-- 錯誤狀態 -->
    <ErrorState v-else-if="error" :kind="error" @retry="retry" />

    <!-- 正常顯示 -->
    <template v-else>
      <!-- 019：分類 Tab 列表（替換 017 的靜態 Tab） -->
      <CategoryTabs
        v-if="categories.length > 0"
        :categories="categories"
        :active-id="activeCategoryId"
        :loading-ids="loadingIds"
        @select="switchCategory"
      />

      <!-- 018：分組 Chips -->
      <SpecGroupChips
        v-if="specGroups.hasGroups.value"
        :groups="specGroups.groups.value"
        :selected-key="specGroups.selectedGroupKey.value"
        @select="specGroups.selectGroup"
      />

      <!-- 商品列表（017：Top 10 排序 + 018：分組篩選） -->
      <section v-if="dashboardItems.length" class="dashboard-list">
        <DashboardCard
          v-for="(di, index) in dashboardItems"
          :key="di.item.id"
          :item="di.item"
          :category-name="activeCategory?.name ?? ''"
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

> **整合要點**：
> - `CategoryTabs` 替換 017 的靜態 Tab `<nav>` 區塊
> - `switchCategory` 傳入 `@select`，由 `useDashboard.switchCategory` 處理（呼叫 `loadCategory` + `resetGroup`）
> - `loadingIds` 由 `isLoadingCategory(activeCategoryId)` 構建
> - 分組 Chips 更新由 `useSpecGroups` 的 `activeCategoryId` watch 自動處理（018 已設計）

---

## 3. API 合約

> **不適用**：本功能為純前端，無後端 API 改動。切換分類的資料載入由 `useItems.loadCategory(id)` 處理（fetch `api/items/{g}.json`，已有的靜態 JSON 端點）。

---

## 4. 資料流

```
使用者點擊 CategoryTabs Tab
  │
  ├─ emit("select", newId)
  │
  ▼
DashboardView.switchCategory(newId)
  │
  ├─ useDashboard.switchCategory(newId)
  │    │
  │    ├─ useItems().loadCategory(newId)
  │    │    ├─ activeCategoryId.value = newId          ← UI 立即切換（快取命中 → 無 fetch）
  │    │    └─ loadedIds.has(newId)?                   ← 判斷快取
  │    │         ├─ 是 → return（<1ms，無 loading）
  │    │         └─ 否 → fetchCategory(newId)          ← 首次載入
  │    │              ├─ inFlight.has(newId)?           ← 併發去重
  │    │              │    ├─ 是 → 等待同一 Promise
  │    │              │    └─ 否 → fetch api/items/{g}.json
  │    │              └─ 完成 → loadedIds.add(newId)
  │    │
  │    └─ resetGroup()                                  ← useSpecGroups 回到「全部」
  │
  ├─ DashboardView 重算 computed
  │    ├─ categoryItems（filteredItems by activeCategoryId）
  │    ├─ specGroups.groupedItems（分組篩選 + 排序）
  │    ├─ dashboardItems（Top 10 + isLowest/lowestPrice）
  │    └─ loadingIds（isLoadingCategory → spinner 顯示）
  │
  └─ UI 更新
       ├─ CategoryTabs：activeTab 反白高亮
       ├─ CategoryTabs：spinner 顯示/消失（僅首次載入）
       ├─ SpecGroupChips：更新為新分類的分組 Chips
       └─ DashboardCard × N：顯示新分類商品
```

**同步性質**：
- `loadCategory` 為 async（可能觸發 fetch），但快取命中時為同步立即返回
- 所有 UI 重算（categoryItems / specGroups / dashboardItems）為 computed（同步響應式），無額外非同步操作
- Spinner 顯示/消失由 `categoryLoading` computed 驅動（async 變化的 reactive 反映）

---

## 5. 邊界條件處理

| 情境 | 來源 | 處理方式 |
|------|------|---------|
| 分類 Tab 超過 5 個時折疊顯示 | BDD @edge-case、IF §5 | CategoryTabs 內部 `needsCollapse` computed：>5 → 顯示前 5 個 + 「更多 ▼」按鈕 |
| 點擊「更多 ▼」展開所有分類 Tab | BDD @edge-case | CategoryTabs `toggleExpand()`：`isExpanded = true` → `visibleCategories` 返回全部 |
| 點擊「收起 ▲」重新折疊分類 Tab | BDD @edge-case | CategoryTabs `toggleExpand()`：`isExpanded = false` → 顯示前 5 個 + 「更多 ▼」按鈕 |
| 分類 Tab 數量 ≤ 5 時不顯示折疊按鈕 | BDD @edge-case | CategoryTabs `needsCollapse`：`categories.length <= 5` → false → 不渲染 toggle button |
| 僅有一個分類時正常顯示 | BDD @edge-case | CategoryTabs 正常渲染 1 個 Tab + 預設選取（useItems bootstrap 自動選第一分類） |
| 快取命中時無 spinner（<1ms 切換） | Tech Decision D3 | `isLoadingCategory(id)` 在 `loadedIds.has(id)` 為 true 時不為 true → loadingIds 為空 Set → 無 spinner |
| 首次載入分類時 spinner 顯示 | Tech Decision D3 | `fetchCategory` 設 `categoryLoading[id] = true` → loadingIds 包含該 ID → spinner 顯示 |
| 切換分類失敗時保留目前顯示的商品 | BDD @error-handling | `useItems.loadCategory` 失敗不 throw（error ref 設值）；`activeCategoryId` 已指向新分類但 items 為空 → EmptyState 顯示；舊分類商品因快取仍在 items 中（只增不減），可切回 |
| 切換分類失敗後重試 | BDD @error-handling | 使用者重新點擊同一 Tab → `switchCategory` → `loadCategory` → `loadedIds` 無該 ID → 重新 fetch |
| 切換分類時取消上一個分類的載入 | BDD @error-handling、Tech Decision D1 | **不主動取消**：useItems 的 `activeCategoryId` 即時切換（UI 即時反映新分類）；舊分類 fetch 完成後 append items（背景），但 UI 不顯示（activeCategoryId 已指向新分類） |
| 新分類無商品時顯示空狀態 | BDD @error-handling、IF §5 | `dashboardItems.length === 0` → `EmptyState` 顯示「暫無商品資料」 |
| 分類 Tab 手機版水平捲動 | Tech Decision §7 風險 | CategoryTabs CSS：`@media (max-width: 768px)` → `overflow-x: auto; flex-wrap: nowrap` |
| 切換分類時間 < 1 秒 | BDD @business-rules、IF §6 | 快取命中 <1ms；首次 fetch 靜態 JSON <200ms（本地檔案）；Playwright performance assertion 驗證 |

---

## 6. CSS 關鍵樣式

| class | 樣式重點 |
|-------|---------|
| `.category-tabs` | `display: flex; align-items: center; gap: 8px; padding: 12px 0; border-bottom: 1px solid var(--color-border);` Tab 列表容器 |
| `.cat-tab` | `padding: 8px 16px; border-radius: 8px; border: 1px solid transparent; background: transparent; color: var(--text); cursor: pointer; transition: all 0.15s ease; white-space: nowrap;` 基礎 Tab 樣式 |
| `.cat-tab:hover` | `background: var(--brand-soft);` 懸停效果（與 CategorySidebar `.cat:hover` 一致） |
| `.cat-tab--active` | `background: var(--brand-soft); color: var(--brand); font-weight: 700; border-color: var(--brand);` 選取高亮（與 CategorySidebar `.cat.is-active` 一致） |
| `.cat-tab--loading` | `opacity: 0.7; cursor: wait;` 載入中態 |
| `.cat-tab__name` | Tab 名稱文字 |
| `.cat-tab__spinner` | `display: inline-block; width: 12px; height: 12px; border: 2px solid var(--text-dim); border-top-color: var(--brand); border-radius: 50%; animation: spin 0.6s linear infinite; margin-left: 4px;` 載入 spinner |
| `.cat-tab--toggle` | `background: none; border: none; color: var(--brand); font-size: 0.85rem; padding: 8px 12px;` 「更多/收起」按鈕（無邊框） |

**動畫**：

```css
@keyframes spin {
  to { transform: rotate(360deg); }
}
```

**響應式**：

```css
@media (max-width: 768px) {
  .category-tabs {
    overflow-x: auto;
    flex-wrap: nowrap;
    scrollbar-width: thin;
    -webkit-overflow-scrolling: touch;
  }
}
```

> CSS class 名稱須與前端 code skeleton 的 class binding 一致。active 樣式與 CategorySidebar 的 `.is-active` 共用 CSS 變數（`--brand-soft`、`--brand`），確保跨頁面一致性。

---

## 7. 開發順序

| 步驟 | 內容 | 依賴 |
|------|------|------|
| 0a | **確認 017 已實作**：`useDashboard.ts`（含 `dashboardItems` computed + `extractCurrentPrice`）+ `DashboardView.vue`（含 Tab 列表 + DashboardCard + ErrorState + EmptyState）+ 路由註冊 `/dashboard` | — |
| 0b | **確認 018 已實作**：`types/specGroup.ts`（GroupOption / GroupStrategy / GROUP_STRATEGY）+ `useSpecGroups.ts`（含 `resetGroup()` 暴露）+ `SpecGroupChips.vue`（含折疊 >8 邏輯） | 0a（useDashboard + useItems 整合） |
| 1 | **新增 `CategoryTabs.vue`**：Tab 列表元件（折疊 >5 + spinner + active 高亮），Props: categories + activeId + loadingIds，Emits: select(id) | — |
| 2 | **新增 `CategoryTabs.test.ts`**：Tab 渲染、折疊/展開、active 高亮、spinner 顯示/隱藏、≤5 時不顯示 toggle | #1 |
| 3 | **修改 `useDashboard.ts`**：新增 `activeCategory` computed + `categoryLoading` computed + `switchCategory(id)` 方法（接收 resetGroup 回呼） | #1（型別） |
| 4 | **修改 `useDashboard.test.ts`**：新增 activeCategory 查詢測試 + categoryLoading 判定測試 + switchCategory 呼叫 loadCategory + resetGroup 測試 | #3 |
| 5 | **確認 `useSpecGroups.ts`**：確認 `resetGroup()` 已在 return 中暴露（若未暴露則補上） | 0b |
| 6 | **修改 `DashboardView.vue`**：import CategoryTabs；整合 switchCategory + loadingIds；替換靜態 Tab 區塊為 `<CategoryTabs>` | #1, #3, #5 |
| 7 | **E2E 測試（Playwright）**：Tab 正確顯示所有分類、預設選取第一個分類、切換 Tab 後列表更新、切換後 SpecGroupChips 更新、>5 個 Tab 時折疊/展開、快取命中時無 spinner、首次載入時 spinner 顯示、切換 <1s | #6 |

> **步驟 0a/0b 為前置確認**：若 017/018 尚未實作，需先完成其開發順序（017 §7 + 018 §8），然後再執行步驟 1–7。DAG 依賴關係：0a → 0b → 1 → 2,3,4,5,6 → 7。

---

## 8. 基礎架構設定

> **不適用**：本功能為純前端，無後端 API 改動、無 Nginx/systemd 設定需求。路由使用 `createWebHashHistory`（GitHub Pages SPA），分類 Tab 為頁面內狀態（不同步至 URL）。

---

## 附錄：BDD Scenario 覆蓋對照表

| BDD Scenario | 對應章節/元件 | 驗證方式 |
|--------------|-------------|---------|
| `@happy-path` Dashboard 載入後顯示分類 Tab 列表 | §2.2 CategoryTabs + §2.5 DashboardView | E2E：骨架屏淡出 → 顯示 Tab 列表 |
| `@happy-path` 預設選取第一個分類並載入商品 | §2.5 DashboardView `watch(categories)` | E2E：載入後自動選取第一 Tab + 顯示商品 |
| `@happy-path` 切換分類 Tab 載入新分類商品 | §2.3 `switchCategory` + §4 資料流 | E2E：點擊 Tab → 列表更新 + Chips 更新 |
| `@happy-path` 切換分類後商品列表正確更新 | §2.5 DashboardView categoryItems | E2E：驗證切換後商品屬於新分類 |
| `@happy-path` 切換分類後分組 Chips 正確更新 | §2.5 DashboardView specGroups | E2E：驗證 Chips 更新為新分類分組 |
| `@happy-path` 快速連續切換分類顯示最新分類商品 | §4 資料流 + useItems inFlight Map | E2E：快速切換 → 最終顯示最後點擊的分類 |
| `@happy-path` 切換分類後顯示載入 spinner | §2.2 CategoryTabs loadingIds + §2.3 categoryLoading | E2E：首次載入新分類 → spinner 出現 → 消失 |
| `@error-handling` 切換分類時取消上一個分類的載入請求 | §5 邊界條件 + Tech Decision D1 | E2E：快速切換 → 僅顯示最新分類（useItems 即時切換） |
| `@error-handling` 新分類無商品時顯示空狀態 | §5 邊界條件 + §2.5 EmptyState | E2E：mock 空分類 → 顯示「暫無商品資料」 |
| `@error-handling` 切換分類失敗時保留目前顯示的商品 | §5 邊界條件 + useItems error ref | E2E：mock 失敗 → 顯示錯誤提示 + 可切回舊分類 |
| `@error-handling` 切換分類失敗後重試 | §5 邊界條件 + useItems retry | E2E：重試 → 重新 fetch |
| `@edge-case` 分類 Tab 超過 5 個時折疊顯示 | §2.2 CategoryTabs `needsCollapse` | E2E：mock 7 個分類 → 前 5 個 + 「更多 ▼」 |
| `@edge-case` 點擊「更多 ▼」展開所有分類 Tab | §2.2 CategoryTabs `toggleExpand` | E2E：點擊「更多」→ 全部顯示 + 「收起 ▲」 |
| `@edge-case` 點擊「收起 ▲」重新折疊分類 Tab | §2.2 CategoryTabs `toggleExpand` | E2E：點擊「收起」→ 前 5 個 + 「更多 ▼」 |
| `@edge-case` 分類 Tab 數量 ≤ 5 時不顯示折疊按鈕 | §2.2 CategoryTabs `needsCollapse` | E2E：mock 5 個分類 → 無 toggle button |
| `@edge-case` 僅有一個分類時正常顯示 | §5 邊界條件 + §2.5 DashboardView | E2E：mock 1 個分類 → 正常顯示 + 預設選取 |
| `@edge-case` 切換分類時間小於 1 秒 | §5 邊界條件 + E2E performance | E2E：Playwright performance assertion |
| `@business-rules` 分類 Tab 列表正確顯示所有分類 | §2.2 CategoryTabs + §2.5 DashboardView | E2E：驗證 Tab 數量與 API 一致 |
| `@business-rules` 預設選取第一個分類 | §2.5 DashboardView `watch(categories)` | E2E：驗證第一 Tab active |
| `@business-rules` 切換分類後 Tab 反白高亮 | §2.2 CategoryTabs `--active` class | E2E：驗證切換後 active class 跟隨 |
| `@business-rules` 切換分類後商品列表正確更新 | §2.5 DashboardView categoryItems | E2E：驗證商品屬於新分類 |
| `@business-rules` 切換分類後分組 Chips 正確更新 | §2.5 DashboardView specGroups | E2E：驗證 Chips 更新 |
| `@business-rules` 切換分類時顯示載入 spinner | §2.2 CategoryTabs spinner + §2.3 categoryLoading | E2E：首次載入 → spinner 顯示/消失 |
| `@business-rules` 切換分類時間 < 1 秒 | §5 邊界條件 | E2E：performance assertion |

> 所有 24 個 BDD Scenario（7 Happy Path + 4 Error Handling + 6 Edge Case + 7 Business Rules）均在規格中找到對應。
