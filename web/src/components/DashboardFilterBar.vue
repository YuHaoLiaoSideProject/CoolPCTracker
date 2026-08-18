<!-- web/src/components/DashboardFilterBar.vue — Dashboard 篩選控制項 UI（022）-->
<script setup lang="ts">
import { SORT_OPTIONS } from "@/types/dashboardFilter"
import type { SortMode } from "@/types/dashboardFilter"

defineProps<{
  sortMode: SortMode
  priceMin: number | null
  priceMax: number | null
  availableBrands: string[]
  selectedBrands: Set<string>
  availableCapacities: string[]
  selectedCapacities: Set<string>
  availableRpms: string[]
  selectedRpms: Set<string>
  categoryName: string | null
  resultCount: number
  totalCount: number
  hasActiveFilter: boolean
}>()

const emit = defineEmits<{
  "update:sort": [mode: SortMode]
  "update:price-min": [value: number | null]
  "update:price-max": [value: number | null]
  "update:brands": [brand: string]
  "update:capacities": [capacity: string]
  "update:rpms": [rpm: string]
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

    <!-- 容量篩選（記憶卡 / HDD 專用） -->
    <div v-if="(categoryName === '記憶卡' || categoryName === 'HDD') && availableCapacities.length > 0" class="filter-bar__capacities">
      <label>容量</label>
      <div class="capacity-list">
        <label
          v-for="capacity in availableCapacities"
          :key="capacity"
          class="capacity-item"
        >
          <input
            type="checkbox"
            :checked="selectedCapacities.has(capacity)"
            @change="emit('update:capacities', capacity)"
          />
          <span>{{ capacity }}</span>
        </label>
      </div>
    </div>

    <!-- 轉速篩選（HDD 專用） -->
    <div v-if="categoryName === 'HDD' && availableRpms.length > 0" class="filter-bar__rpms">
      <label>轉速</label>
      <div class="rpm-list">
        <label
          v-for="rpm in availableRpms"
          :key="rpm"
          class="rpm-item"
        >
          <input
            type="checkbox"
            :checked="selectedRpms.has(rpm)"
            @change="emit('update:rpms', rpm)"
          />
          <span>{{ rpm }}</span>
        </label>
      </div>
    </div>

    <!-- 品牌篩選（非記憶卡/HDD 分類） -->
    <div v-if="categoryName !== '記憶卡' && categoryName !== 'HDD' && availableBrands.length > 0" class="filter-bar__brands">
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
  font-size: 0.85rem;
}

.price-input::placeholder {
  color: var(--text-dim);
  opacity: 0.6;
}

.price-sep {
  color: var(--text-dim);
}

.filter-bar__brands,
.filter-bar__capacities,
.filter-bar__rpms {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filter-bar__brands label,
.filter-bar__capacities label,
.filter-bar__rpms label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-dim);
}

.brand-list,
.capacity-list,
.rpm-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.brand-item,
.capacity-item,
.rpm-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.85rem;
  color: var(--text);
  cursor: pointer;
}

.brand-item input,
.capacity-item input,
.rpm-item input {
  width: 14px;
  height: 14px;
  accent-color: var(--primary);
  cursor: pointer;
}

.filter-bar__footer {
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

.clear-btn {
  padding: 6px 12px;
  font-size: 0.82rem;
  color: var(--primary);
  background: transparent;
  border: 1px solid var(--primary);
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.clear-btn:hover {
  background: var(--primary);
  color: white;
}
</style>
