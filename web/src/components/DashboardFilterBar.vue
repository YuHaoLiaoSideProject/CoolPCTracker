<!-- web/src/components/DashboardFilterBar.vue — Dashboard 篩選控制項 UI（022）-->
<script setup lang="ts">
import { SORT_OPTIONS } from "@/types/dashboardFilter"
import type { SortMode } from "@/types/dashboardFilter"

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
  "update:sort": [mode: SortMode]
  "update:price-min": [value: number | null]
  "update:price-max": [value: number | null]
  "update:brands": [brand: string]
  clear: []
}>()

function onSortChange(e: Event) {
  emit("update:sort", (e.target as HTMLSelectElement).value as SortMode)
}

function onPriceMinChange(e: Event) {
  const raw = (e.target as HTMLInputElement).value
  emit("update:price-min", raw === "" ? null : Number(raw))
}

function onPriceMaxChange(e: Event) {
  const raw = (e.target as HTMLInputElement).value
  emit("update:price-max", raw === "" ? null : Number(raw))
}
</script>

<template>
  <div class="filter-bar" role="search" aria-label="商品篩選與排序">
    <!-- 排序 -->
    <div class="filter-bar__sort">
      <label for="sort-select">排序</label>
      <select
        id="sort-select"
        class="sort-select"
        :value="sortMode"
        @change="onSortChange"
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

    <!-- 價格範圍 -->
    <div class="filter-bar__price">
      <label>價格範圍</label>
      <input
        type="number"
        class="price-input"
        placeholder="下限"
        :value="priceMin ?? ''"
        min="0"
        @change="onPriceMinChange"
      />
      <span class="price-sep">–</span>
      <input
        type="number"
        class="price-input"
        placeholder="上限"
        :value="priceMax ?? ''"
        min="0"
        @change="onPriceMaxChange"
      />
    </div>

    <!-- 品牌篩選 -->
    <div v-if="availableBrands.length > 0" class="filter-bar__brands">
      <label>品牌</label>
      <div class="brand-list">
        <label
          v-for="brand in availableBrands"
          :key="brand"
          class="brand-item"
        >
          <input
            type="checkbox"
            :checked="selectedBrands.has(brand)"
            @change="emit('update:brands', brand)"
          />
          <span>{{ brand }}</span>
        </label>
      </div>
    </div>

    <!-- Footer -->
    <div class="filter-bar__footer">
      <span class="result-count">{{ resultCount }} / {{ totalCount }} 件商品</span>
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

.filter-bar__sort {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-bar__sort label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-dim);
  flex-shrink: 0;
}

.sort-select {
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text);
}

.filter-bar__price {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-bar__price label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-dim);
  flex-shrink: 0;
}

.price-input {
  width: 100px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.price-sep {
  color: var(--text-dim);
  flex-shrink: 0;
}

.filter-bar__brands {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.filter-bar__brands > label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-dim);
  flex-shrink: 0;
  padding-top: 4px;
}

.brand-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  max-height: 80px;
  overflow-y: auto;
}

.brand-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.82rem;
  cursor: pointer;
  white-space: nowrap;
}

.brand-item input[type="checkbox"] {
  cursor: pointer;
}

.filter-bar__footer {
  display: flex;
  align-items: center;
  gap: 12px;
}

.result-count {
  font-size: 0.82rem;
  color: var(--text-dim);
}

.clear-btn {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 12px;
  background: transparent;
  color: var(--brand);
  font-size: 0.82rem;
  font-weight: 600;
  transition: background-color var(--transition);
}

.clear-btn:hover {
  background: var(--brand-soft);
}

/* ── RWD ────────────────────────────────────────────── */
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
}
</style>
