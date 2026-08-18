<!-- web/src/views/DashboardView.vue — Dashboard 頁面（017 + 018 + 019 整合）-->
<!-- 整合 CategoryTabs + SpecGroupChips + DashboardCard + DashboardSkeleton + ErrorState + EmptyState -->
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

// —— Dashboard 邏輯（017 + 019）——
const { dashboardItems, activeCategory, switchCategory } = useDashboard(
  categoryItems,
  activeCategoryId,
  specGroups.resetGroup,
)

// —— loadingIds（CategoryTabs spinner 用）——
const loadingIds = computed(() => {
  const s = new Set<string>()
  const id = activeCategoryId.value
  if (id && isLoadingCategory(id)) s.add(id)
  return s
})

// —— 預設選取第一個分類 ——
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
    <!-- 骨架屏 -->
    <DashboardSkeleton v-if="loading && !dashboardItems.length" />

    <!-- 錯誤狀態 -->
    <ErrorState v-else-if="error" :kind="error" @retry="retry" />

    <!-- 正常顯示 -->
    <template v-else>
      <!-- 分類 Tab 列表（019：CategoryTabs） -->
      <CategoryTabs
        v-if="categories.length > 0"
        :categories="categories"
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

      <!-- 商品列表 -->
      <section v-if="dashboardItems.length" class="dashboard-list" aria-label="商品列表">
        <DashboardCard
          v-for="di in dashboardItems"
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
