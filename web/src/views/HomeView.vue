<!-- web/src/views/HomeView.vue — 統一首頁（重構自 ListingView + Dashboard 功能整合）-->
<!-- 整合 CategoryTabs + SearchBar + SpecFilterPanel + 排序下拉 + ProductCard -->
<!-- 設計規格：docs/uiux/024-home-integration-redesign.md -->
<script setup lang="ts">
import { computed, watch, ref, onMounted } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useItems } from "@/composables/useItems"
import { useFilters } from "@/composables/useFilters"
import { isCategoryKey, labelOf } from "@/data/categories"
import { formatDateTime } from "@/utils/format"
import type { Item } from "@/types/item"
import type { SortMode } from "@/types/dashboardFilter"
import { SORT_OPTIONS } from "@/types/dashboardFilter"
import CategoryTabs from "@/components/CategoryTabs.vue"
import SearchBar from "@/components/SearchBar.vue"
import SpecFilterPanel from "@/components/SpecFilterPanel.vue"
import ProductList from "@/components/ProductList.vue"
import ErrorState from "@/components/ErrorState.vue"

const ALL = "all" // URL ?category=all = 全部視圖

const route = useRoute()
const router = useRouter()
const {
  items, meta, loading, error, retry, isStale,
  categories, activeCategoryId, itemToCategory,
  loadCategory, loadAll, isLoadingCategory,
} = useItems()
const filters = useFilters(items, itemToCategory, activeCategoryId)
const { keyword, conditions, filteredItems, addCondition, removeCondition, clearAll } = filters

// —— 排序狀態 ——
const sortMode = ref<SortMode>("price_asc")

// —— 「全部」分類顯示計算 ——
const allTotal = computed(() => categories.value.reduce((a, c) => a + c.count, 0))

/** 在 categories 前面插入「全部」虛擬分類供 CategoryTabs 使用 */
const tabsCategories = computed(() => [
  { id: ALL, name: "全部", file: "", count: allTotal.value },
  ...categories.value,
])

/** CategoryTabs loading 狀態（含「全部」） */
const loadingIds = computed(() => {
  const s = new Set<string>()
  // 「全部」= activeCategoryId 為 null 時
  if (activeCategoryId.value === null && loading.value) s.add(ALL)
  // 各分類
  for (const c of categories.value) {
    if (isLoadingCategory(c.id)) s.add(c.id)
  }
  return s
})

// —— URL 參數解析 ——
function resolveParam(v: unknown): string | null | typeof ALL {
  if (v === ALL) return ALL
  if (typeof v === "string" && categories.value.some(c => c.id === v)) return v
  if (isCategoryKey(v)) {
    const c = categories.value.find(c => c.name === labelOf(v))
    if (c) return c.id
  }
  return null
}

/** 套用目前 URL 至資料層 */
function applyUrlToState(): void {
  const id = resolveParam(route.query.category)
  if (id === ALL) {
    void loadAll()
  } else if (id) {
    void loadCategory(id)
  } else {
    // 無參數 → 預設第一個分類
    const first = categories.value[0]?.id ?? null
    if (first) void loadCategory(first)
  }
}
watch(categories, applyUrlToState, { immediate: true })

// —— 分類選擇（CategoryTabs 點擊） ——
function selectCategory(id: string) {
  if (id === ALL) {
    router.replace({ query: { category: ALL } })
    void loadAll()
  } else {
    router.replace({ query: { category: id } })
    void loadCategory(id)
  }
}
watch(
  () => route.query.category,
  () => applyUrlToState(),
)

// —— 全站搜尋：非空關鍵字 → 切至「全部」——
watch(keyword, (k, prev) => {
  if (k.trim() && !prev?.trim()) {
    void loadAll()
    router.replace({ query: { category: ALL } })
  }
})

// —— 排序後的商品列表 ——
const sortedItems = computed<Item[]>(() => {
  const mode = sortMode.value
  const list = [...filteredItems.value]

  list.sort((a, b) => {
    if (mode === "recently_updated") {
      return b.last_seen.localeCompare(a.last_seen)
    }
    // price sort：null 置底
    const pa = a.history.length > 0 ? a.history[a.history.length - 1].p : null
    const pb = b.history.length > 0 ? b.history[b.history.length - 1].p : null
    if (pa == null && pb == null) return 0
    if (pa == null) return 1
    if (pb == null) return -1
    return mode === "price_asc" ? pa - pb : pb - pa
  })

  return list
})

// —— 卡片需要分類名 ——
const categoryNames = computed<Record<string, string>>(() => {
  const nameById = new Map(categories.value.map(c => [c.id, c.name]))
  const out: Record<string, string> = {}
  for (const [iid, cid] of itemToCategory.value) {
    const n = nameById.get(cid)
    if (n) out[iid] = n
  }
  return out
})

// —— 目前視圖的未過濾總數 ——
const universeTotal = computed(() => {
  if (activeCategoryId.value) {
    let n = 0
    for (const cid of itemToCategory.value.values()) if (cid === activeCategoryId.value) n += 1
    return n
  }
  return items.value.length
})

// —— 事件處理 ——
function onOpen(item: Item) {
  router.push({ path: `/product/${encodeURIComponent(item.id)}`, query: route.query })
}

function onClearAll() {
  const wasCategoryEmpty = keyword.value.trim() === "" && conditions.value.length === 0
  clearAll()
  if (wasCategoryEmpty) selectCategory(ALL)
}

// —— 錯誤/舊資料分流 ——
const showError = computed(() => !!error.value && !loading.value && sortedItems.value.length === 0)
const showOldData = computed(() => !!error.value && !loading.value && sortedItems.value.length > 0)

// —— 背景預載詳情頁 chunk ——
onMounted(() => {
  const prefetch = () => import("@/views/ProductDetailView.vue")
  const ric = (window as any).requestIdleCallback
  if (typeof ric === "function") {
    ric(() => { prefetch().catch(() => {}) }, { timeout: 2000 })
  } else {
    setTimeout(() => { prefetch().catch(() => {}) }, 500)
  }
})
</script>

<template>
  <div class="home-view">
    <Transition name="fade">
      <div v-if="isStale" class="stale-banner" role="alert">
        資料可能已過期（最後更新：{{ formatDateTime(meta?.crawled_at) }}）
      </div>
    </Transition>

    <!-- 分類 Tab 列表（含「全部」） -->
    <CategoryTabs
      v-if="tabsCategories.length > 0"
      :categories="tabsCategories"
      :active-id="activeCategoryId ?? ALL"
      :loading-ids="loadingIds"
      @select="selectCategory"
    />

    <!-- 工具列：搜尋 + 規格篩選 + 排序 -->
    <div class="home-toolbar">
      <div class="toolbar-row toolbar-row--primary">
        <SearchBar v-model="keyword" />
        <div class="sort-wrapper">
          <label for="home-sort" class="sort-label">排序</label>
          <select
            id="home-sort"
            class="sort-select"
            :value="sortMode"
            @change="sortMode = ($event.target as HTMLSelectElement).value as SortMode"
          >
            <option
              v-for="opt in SORT_OPTIONS"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </div>
      </div>
      <SpecFilterPanel
        :conditions="conditions"
        @add="addCondition"
        @remove="removeCondition"
      />
    </div>

    <!-- 骨架屏 -->
    <div v-if="loading && !sortedItems.length" class="skeleton-list" aria-busy="true">
      <div v-for="n in 6" :key="n" class="sk" />
    </div>

    <!-- 錯誤狀態 -->
    <ErrorState v-else-if="showError" :kind="error!" @retry="retry" />

    <!-- 正常顯示 -->
    <template v-else>
      <div v-if="showOldData" class="stale-banner" role="alert">
        資料載入失敗，目前顯示上次成功載入的資料。
      </div>
      <ProductList
        :items="sortedItems"
        :total="universeTotal"
        :keyword="keyword"
        :conditions="conditions"
        :category-names="categoryNames"
        @clear-all="onClearAll"
        @open="onOpen"
      />
    </template>
  </div>
</template>

<style scoped>
.home-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 工具列 */
.home-toolbar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 14px;
  box-shadow: var(--shadow);
}

.toolbar-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-row--primary {
  flex-wrap: wrap;
}

/* 排序下拉 */
.sort-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.sort-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-dim);
  white-space: nowrap;
}

.sort-select {
  height: var(--h);
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text);
  font-size: 0.85rem;
}

/* 過期橫幅 */
.stale-banner {
  background: var(--warn-bg);
  border: 1px solid var(--warn-border);
  color: var(--warn-text);
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 0.85rem;
  text-align: center;
}

/* 骨架屏 */
.skeleton-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.skeleton-list .sk {
  height: 120px;
  border-radius: var(--radius);
  background: linear-gradient(90deg, #eee 25%, #f5f5f5 50%, #eee 75%);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
}

@keyframes shimmer {
  to { background-position: -200% 0; }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* RWD：平板 */
@media (max-width: 1023px) {
  .home-view {
    padding: 14px;
  }
}

/* RWD：手機 */
@media (max-width: 639px) {
  .home-view {
    padding: 10px;
    gap: 12px;
  }

  .home-toolbar {
    padding: 10px 12px;
  }

  .toolbar-row--primary {
    flex-direction: column;
    align-items: stretch;
  }

  .sort-wrapper {
    width: 100%;
  }

  .sort-select {
    height: var(--h-mobile);
    flex: 1;
  }
}
</style>
