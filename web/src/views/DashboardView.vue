<!-- web/src/views/DashboardView.vue — Dashboard 頁面（017 + 018 + 019 + 022 整合）-->
<!-- 整合 CategoryTabs + SpecGroupChips + DashboardFilterBar + DashboardCard + DashboardSkeleton + ErrorState + EmptyState -->
<script setup lang="ts">
import { computed, watch } from "vue"
import { useItems } from "@/composables/useItems"
import { useDashboard } from "@/composables/useDashboard"
import { useSpecGroups } from "@/composables/useSpecGroups"
import { useDashboardFilters } from "@/composables/useDashboardFilters"
import type { DashboardItem } from "@/composables/useDashboard"
import CategoryTabs from "@/components/CategoryTabs.vue"
import SpecGroupChips from "@/components/SpecGroupChips.vue"
import DashboardFilterBar from "@/components/DashboardFilterBar.vue"
import DashboardCard from "@/components/DashboardCard.vue"
import DashboardSkeleton from "@/components/DashboardSkeleton.vue"
import ErrorState from "@/components/ErrorState.vue"
import EmptyState from "@/components/EmptyState.vue"

const {
  items,
  categories,
  activeCategoryId,
  loading,
  error,
  retry,
  itemToCategory,
  loadCategory,
  isLoadingCategory,
} = useItems()

// —— Dashboard 分類篩選：僅顯示 dashboardVisible=true 的分類 ——
const dashboardCategories = computed(() =>
  categories.value.filter((c) => c.dashboardVisible !== false),
)

// —— 分類過濾 ——
const categoryItems = computed(() => {
  const id = activeCategoryId.value
  if (id == null) return []
  return items.value.filter((item) => itemToCategory.value.get(item.id) === id)
})

// —— 分組（018）——
const categoryName = computed(() => {
  const id = activeCategoryId.value
  return id ? categories.value.find((c) => c.id === id)?.name ?? null : null
})
const specGroups = useSpecGroups(categoryItems, categoryName)

// —— 篩選 + 排序（022）——
const dashboardFilters = useDashboardFilters(categoryItems)

// —— Dashboard 邏輯（017 + 019）：取 activeCategory / switchCategory ——
const { extractCurrentPrice, activeCategory, switchCategory } = useDashboard(
  categoryItems,
  activeCategoryId,
  specGroups.resetGroup,
)

// —— 顯示商品（分組 ∩ 篩選排序 → DashboardItem[]）——
const groupedIds = computed(() => {
  return new Set(specGroups.groupedItems.value.map((i) => i.id))
})

const displayItems = computed(() =>
  dashboardFilters.sortedItems.value.filter((i) => groupedIds.value.has(i.id)),
)

const displayDashboardItems = computed<DashboardItem[]>(() => {
  const list = displayItems.value
  if (list.length === 0) return []

  // 計算分類最低價
  let lowestPrice: number | null = null
  let lowestId: string | null = null
  for (const item of list) {
    const price = extractCurrentPrice(item)
    if (price != null && (lowestPrice == null || price < lowestPrice)) {
      lowestPrice = price
      lowestId = item.id
    }
  }

  return list.map((item) => ({
    item,
    currentPrice: extractCurrentPrice(item),
    isLowest: lowestId != null && item.id === lowestId,
    lowestPrice,
  }))
})

// —— loadingIds（CategoryTabs spinner 用）——
const loadingIds = computed(() => {
  const s = new Set<string>()
  const id = activeCategoryId.value
  if (id && isLoadingCategory(id)) s.add(id)
  return s
})

// —— 篩選空狀態處理 ——
function handleFilterClear() {
  dashboardFilters.clearFilters()
}

// —— 預設選取第一個分類 ——
watch(
  dashboardCategories,
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
    <!-- 骨架屏 -->
    <DashboardSkeleton v-if="loading && !displayDashboardItems.length" />

    <!-- 錯誤狀態 -->
    <ErrorState v-else-if="error" :kind="error" @retry="retry" />

    <!-- 正常顯示 -->
    <template v-else>
      <!-- 分類 Tab 列表（019：CategoryTabs） -->
      <CategoryTabs
        v-if="dashboardCategories.length > 0"
        :categories="dashboardCategories"
        :active-id="activeCategoryId"
        :loading-ids="loadingIds"
        @select="switchCategory"
      />

      <!-- 分組 Chips（018） -->
      <SpecGroupChips
        v-if="specGroups.hasGroups.value"
        :groups="specGroups.groups.value"
        :selected-key="specGroups.selectedGroupKey.value"
        @select="specGroups.selectGroup"
      />

      <!-- 篩選控制項（022） -->
      <DashboardFilterBar
        v-if="categoryItems.length > 0"
        :sort-mode="dashboardFilters.sortMode.value"
        :price-min="dashboardFilters.priceMin.value"
        :price-max="dashboardFilters.priceMax.value"
        :available-brands="dashboardFilters.availableBrands.value"
        :selected-brands="dashboardFilters.selectedBrands.value"
        :result-count="displayItems.length"
        :total-count="categoryItems.length"
        :has-active-filter="dashboardFilters.hasActiveFilter.value"
        @update:sort="dashboardFilters.setSortMode"
        @update:price-min="dashboardFilters.setPriceMin"
        @update:price-max="dashboardFilters.setPriceMax"
        @update:brands="dashboardFilters.toggleBrand"
        @clear="handleFilterClear"
      />

      <!-- 商品列表 -->
      <section v-if="displayDashboardItems.length" class="dashboard-list" aria-label="商品列表">
        <DashboardCard
          v-for="di in displayDashboardItems"
          :key="di.item.id"
          :item="di.item"
          :category-name="activeCategory?.name ?? ''"
          :is-lowest="di.isLowest"
          :lowest-price="di.lowestPrice"
        />
      </section>

      <!-- 篩選空狀態 -->
      <EmptyState
        v-else-if="dashboardFilters.hasActiveFilter.value"
        kind="filter"
        @clear="handleFilterClear"
      />

      <!-- 分類空狀態 -->
      <EmptyState v-else kind="category" />
    </template>
  </main>
</template>

<style scoped>
.dashboard-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dashboard-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

@media (max-width: 768px) {
  .dashboard-view {
    padding: 14px;
  }
}

@media (max-width: 639px) {
  .dashboard-view {
    padding: 10px;
  }
  .dashboard-list {
    grid-template-columns: 1fr;
    gap: 10px;
  }
}
</style>
