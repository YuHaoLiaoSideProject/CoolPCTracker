<script setup lang="ts">
// web/src/components/ProductList.vue — 列表容器（開發規格 003 §2.10）
// 標題＋命中筆數（x / total）、空狀態分流（search/filter/category）、清除全部、
// 渲染商品卡片。
import { computed } from "vue"
import ProductCard from "./ProductCard.vue"
import EmptyState from "./EmptyState.vue"
import type { Item } from "@/types/item"
import type { SpecCondition } from "@/types/filters"

const props = defineProps<{
  items: Item[]
  total: number // 未過濾前總筆數（標題顯示「x / total」）
  keyword: string
  conditions: SpecCondition[]
  categoryNames?: Record<string, string> // itemId → 分類名（v2：卡片 chips 需分類名，由外部對照）
}>()

const emit = defineEmits<{
  (e: "clear-all"): void
  (e: "open", item: Item): void
}>()

const hasActiveFilter = computed(
  () => props.keyword.trim() !== "" || props.conditions.length > 0,
)

/** 空狀態分流：優先搜尋無結果 → 篩選無結果 → 空分類（§6.2） */
const emptyKind = computed<"search" | "filter" | "category">(() => {
  if (props.keyword.trim()) return "search"
  if (props.conditions.length) return "filter"
  return "category"
})

const conditionLabels = computed(() => props.conditions.map(c => c.label))
</script>

<template>
  <section class="product-list" aria-label="商品列表">
    <div class="pl-header">
      <h2 class="pl-title">商品列表</h2>
      <span class="pl-count" aria-live="polite">
        共 <b>{{ items.length }}</b> / {{ total }} 筆
      </span>
      <button
        v-if="hasActiveFilter"
        type="button"
        class="pl-clear"
        @click="emit('clear-all')"
      >
        清除全部條件
      </button>
    </div>

    <div v-if="items.length" class="cat-grid">
      <ProductCard
        v-for="it in items"
        :key="it.id"
        :item="it"
        :category-name="categoryNames?.[it.id] ?? ''"
        @open="emit('open', $event)"
      />
    </div>

    <EmptyState
      v-else
      :kind="emptyKind"
      :keyword="keyword.trim() || undefined"
      :conditions="conditionLabels"
      @clear="emit('clear-all')"
    />
  </section>
</template>

<style scoped>
.product-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.pl-header {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 10px;
}

.pl-title {
  font-size: 1.05rem;
  font-weight: 700;
}

.pl-count {
  font-size: 0.78rem;
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
}

.pl-count b {
  color: var(--text);
  font-weight: 700;
}

.pl-clear {
  margin-left: auto;
  height: var(--h);
  padding: 0 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-dim);
  font-size: 0.8rem;
  font-weight: 600;
  transition: color var(--transition), border-color var(--transition);
}

.pl-clear:hover {
  color: var(--brand);
  border-color: var(--brand);
}

.cat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

@media (max-width: 639px) {
  .cat-grid {
    grid-template-columns: 1fr;
  }

  .pl-clear {
    height: var(--h-mobile);
  }
}
</style>
