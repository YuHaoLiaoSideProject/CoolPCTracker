<!-- web/src/views/HomeView.vue — 統一首頁（重構自 ListingView + Dashboard 功能整合）-->
<!-- 整合 CategoryTabs + SearchBar + SpecFilterPanel + DashboardFilterBar checkbox 篩選 -->
<!-- 設計規格：docs/uiux/024-home-integration-redesign.md -->
<script setup lang="ts">
import { computed, watch, ref, onMounted } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useItems } from "@/composables/useItems"
import { useFilters } from "@/composables/useFilters"
import { useDashboardFilters } from "@/composables/useDashboardFilters"
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

// —— 搜尋 + 規格條件篩選（來自 ListingView）——
const filters = useFilters(items, itemToCategory, activeCategoryId)
const { keyword, conditions, filteredItems, addCondition, removeCondition, clearAll } = filters

// —— Dashboard 風格 checkbox 篩選（價格 / 品牌 / 容量 / 轉速 / DDR / 介面）——
const {
  sortMode, priceMin, priceMax,
  selectedBrands, selectedCapacities, selectedRpms,
  selectedRamCapacities, selectedDdrTypes, selectedInterfaces,
  availableBrands, availableCapacities, availableRpms,
  availableRamCapacities, availableDdrTypes, availableInterfaces,
  hasActiveFilter: hasDashboardFilter,
  filteredItems: dashboardFilteredItems,
  toggleBrand, toggleCapacity, toggleRpm,
  toggleRamCapacity, toggleDdrType, toggleInterface,
  setPriceMin, setPriceMax,
  clearFilters: clearDashboardFilters,
} = useDashboardFilters(filteredItems)

// —— 進階篩選折疊 ——
const isExpanded = ref(window.innerWidth >= 1024)

// —— 目前選中分類名稱（用於 conditional 顯示篩選群組）——
const currentCategoryName = computed(() => {
  if (!activeCategoryId.value) return null
  const cat = categories.value.find(c => c.id === activeCategoryId.value)
  return cat?.name ?? null
})

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
  if (activeCategoryId.value === null && loading.value) s.add(ALL)
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
    const first = categories.value[0]?.id ?? null
    if (first) void loadCategory(first)
  }
}
watch(categories, applyUrlToState, { immediate: true })

// —— 分類選擇（CategoryTabs 點擊）——
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

// —— 最終排序後的商品列表 ——
const sortedItems = computed<Item[]>(() => {
  const mode = sortMode.value
  const list = [...dashboardFilteredItems.value]

  list.sort((a, b) => {
    if (mode === "recently_updated") {
      return b.last_seen.localeCompare(a.last_seen)
    }
    if (mode === "name_asc" || mode === "name_desc") {
      const cmp = a.name.localeCompare(b.name)
      return mode === "name_asc" ? cmp : -cmp
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

// —— 是否有篩選條件 ——
const hasActiveFilters = computed(() => {
  return (
    keyword.value.trim() !== "" ||
    conditions.value.length > 0 ||
    hasDashboardFilter.value
  )
})

/** 清除所有篩選條件（不含搜尋） */
function clearFilters() {
  conditions.value.forEach(c => removeCondition(c.id))
  clearDashboardFilters()
}

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
  clearDashboardFilters()
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

    <!-- 工具列：搜尋 + 篩選 + 排序 -->
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

      <!-- 進階篩選 Toggle -->
      <button
        class="filter-expand-btn"
        @click="isExpanded = !isExpanded"
        :aria-expanded="isExpanded"
        aria-controls="filter-advanced"
      >
        {{ isExpanded ? '收起篩選 ▲' : '更多篩選 ▼' }}
      </button>

      <!-- 進階篩選區 -->
      <div
        id="filter-advanced"
        class="filter-advanced"
        :class="{ collapsed: !isExpanded }"
      >
        <!-- 價格範圍 -->
        <div class="filter-group">
          <label>價格範圍</label>
          <input
            type="number"
            class="price-input"
            placeholder="下限"
            :value="priceMin ?? ''"
            min="0"
            @change="setPriceMin(($event.target as HTMLInputElement).value === '' ? null : Number(($event.target as HTMLInputElement).value))"
          />
          <span class="price-sep">–</span>
          <input
            type="number"
            class="price-input"
            placeholder="上限"
            :value="priceMax ?? ''"
            min="0"
            @change="setPriceMax(($event.target as HTMLInputElement).value === '' ? null : Number(($event.target as HTMLInputElement).value))"
          />
        </div>

        <!-- 品牌篩選（所有分類） -->
        <div v-if="availableBrands.length > 0" class="filter-group">
          <label>品牌</label>
          <div class="chip-list">
            <label
              v-for="brand in availableBrands"
              :key="brand"
              class="chip-item"
            >
              <input
                type="checkbox"
                :checked="selectedBrands.has(brand)"
                @change="toggleBrand(brand)"
              />
              <span>{{ brand }}</span>
            </label>
          </div>
        </div>

        <!-- 容量篩選（SSD / HDD / 記憶卡） -->
        <div
          v-if="(currentCategoryName === 'SSD' || currentCategoryName === 'HDD' || currentCategoryName === '記憶卡') && availableCapacities.length > 0"
          class="filter-group"
        >
          <label>容量</label>
          <div class="chip-list">
            <label
              v-for="capacity in availableCapacities"
              :key="capacity"
              class="chip-item"
            >
              <input
                type="checkbox"
                :checked="selectedCapacities.has(capacity)"
                @change="toggleCapacity(capacity)"
              />
              <span>{{ capacity }}</span>
            </label>
          </div>
        </div>

        <!-- 轉速篩選（HDD） -->
        <div
          v-if="currentCategoryName === 'HDD' && availableRpms.length > 0"
          class="filter-group"
        >
          <label>轉速</label>
          <div class="chip-list">
            <label
              v-for="rpm in availableRpms"
              :key="rpm"
              class="chip-item"
            >
              <input
                type="checkbox"
                :checked="selectedRpms.has(rpm)"
                @change="toggleRpm(rpm)"
              />
              <span>{{ rpm }}</span>
            </label>
          </div>
        </div>

        <!-- 記憶體容量篩選（記憶體） -->
        <div
          v-if="currentCategoryName === '記憶體' && availableRamCapacities.length > 0"
          class="filter-group"
        >
          <label>容量</label>
          <div class="chip-list">
            <label
              v-for="ramCap in availableRamCapacities"
              :key="ramCap"
              class="chip-item"
            >
              <input
                type="checkbox"
                :checked="selectedRamCapacities.has(ramCap)"
                @change="toggleRamCapacity(ramCap)"
              />
              <span>{{ ramCap }}</span>
            </label>
          </div>
        </div>

        <!-- DDR 類型篩選（記憶體） -->
        <div
          v-if="currentCategoryName === '記憶體' && availableDdrTypes.length > 0"
          class="filter-group"
        >
          <label>DDR 類型</label>
          <div class="chip-list">
            <label
              v-for="ddr in availableDdrTypes"
              :key="ddr"
              class="chip-item"
            >
              <input
                type="checkbox"
                :checked="selectedDdrTypes.has(ddr)"
                @change="toggleDdrType(ddr)"
              />
              <span>{{ ddr }}</span>
            </label>
          </div>
        </div>

        <!-- SSD 介面篩選（SSD） -->
        <div
          v-if="currentCategoryName === 'SSD' && availableInterfaces.length > 0"
          class="filter-group"
        >
          <label>介面</label>
          <div class="chip-list">
            <label
              v-for="iface in availableInterfaces"
              :key="iface"
              class="chip-item"
            >
              <input
                type="checkbox"
                :checked="selectedInterfaces.has(iface)"
                @change="toggleInterface(iface)"
              />
              <span>{{ iface }}</span>
            </label>
          </div>
        </div>

        <!-- 規格條件（VRAM / CPU核數 / TDP 等） -->
        <SpecFilterPanel
          :conditions="conditions"
          @add="addCondition"
          @remove="removeCondition"
        />
      </div>

      <!-- 結果計數 + 清除篩選 -->
      <div v-if="hasActiveFilters" class="filter-footer">
        <span class="result-count">找到 <b>{{ sortedItems.length }}</b> 筆</span>
        <button class="clear-btn" @click="clearFilters">清除篩選</button>
      </div>
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

/* 進階篩選 Toggle */
.filter-expand-btn {
  height: var(--h);
  padding: 0 12px;
  border: none;
  background: none;
  color: var(--brand);
  font-size: 0.85rem;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
  align-self: flex-start;
}
.filter-expand-btn:hover {
  background: var(--brand-soft);
  border-radius: var(--radius-sm);
}

/* 進階篩選區 */
.filter-advanced {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px 0;
  border-top: 1px solid var(--border);
  margin-top: 4px;
  overflow: hidden;
  transition: max-height 200ms ease, padding 200ms ease;
  max-height: 600px;
}
.filter-advanced.collapsed {
  max-height: 0;
  padding: 0;
  border: none;
  margin-top: 0;
}

/* 篩選群組 */
.filter-group {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
}
.filter-group label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-dim);
  min-width: 50px;
  padding-top: 4px;
}

/* Checkbox chip list（Dashboard 風格） */
.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 28px;
  padding: 0 10px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-dim);
  font-size: 0.78rem;
  cursor: pointer;
  transition: all var(--transition);
  white-space: nowrap;
}
.chip-item:hover {
  border-color: var(--brand);
  color: var(--brand);
}
.chip-item:has(input:checked) {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
.chip-item input[type="checkbox"] {
  width: 0;
  height: 0;
  margin: 0;
  padding: 0;
  opacity: 0;
  position: absolute;
}

/* 價格輸入 */
.price-input {
  width: 90px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text);
  font-size: 0.85rem;
}
.price-input:focus {
  border-color: var(--accent);
  outline: none;
}
.price-sep {
  color: var(--text-dim);
}

/* 篩選結果列 */
.filter-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}
.result-count {
  font-size: 0.82rem;
  color: var(--text-dim);
}
.result-count b {
  color: var(--brand);
}
.clear-btn {
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--brand);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--brand);
  font-size: 0.82rem;
  cursor: pointer;
  transition: all var(--transition);
}
.clear-btn:hover {
  background: var(--brand);
  color: #fff;
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
  to { background-position: -200% 100%; }
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

  .toolbar-row--primary {
    flex-direction: column;
    align-items: stretch;
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
