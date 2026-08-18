<!-- web/src/components/CategoryTabs.vue — 分類 Tab 列表（開發規格 019 §2.2）-->
<!-- 折疊 >5 → 前 5 個 + 「更多 ▼」；Spinner；Active 高亮；RWD 水平捲動 -->
<script setup lang="ts">
import { ref, computed } from "vue"
import type { CategoryMeta } from "@/types/item"

const COLLAPSE_THRESHOLD = 5

const props = defineProps<{
  categories: CategoryMeta[]
  activeId: string | null
  loadingIds: Set<string>
}>()

const emit = defineEmits<{
  (e: "select", id: string): void
}>()

const isExpanded = ref(false)

const needsCollapse = computed(() => props.categories.length > COLLAPSE_THRESHOLD)

const visibleCategories = computed(() => {
  if (!needsCollapse.value || isExpanded.value) return props.categories
  return props.categories.slice(0, COLLAPSE_THRESHOLD)
})

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

<style scoped>
.category-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}

.cat-tab {
  display: inline-flex;
  align-items: center;
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text);
  font-size: 0.88rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.cat-tab:hover {
  background: var(--brand-soft);
}

.cat-tab--active {
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 700;
  border-color: var(--brand);
}

.cat-tab--loading {
  opacity: 0.7;
  cursor: wait;
}

.cat-tab__name {
  /* baseline text */
}

.cat-tab__spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--text-dim);
  border-top-color: var(--brand);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  margin-left: 4px;
}

.cat-tab--toggle {
  background: none;
  border: none;
  color: var(--brand);
  font-size: 0.85rem;
  font-weight: 500;
  padding: 8px 12px;
}

.cat-tab--toggle:hover {
  background: var(--brand-soft);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 768px) {
  .category-tabs {
    overflow-x: auto;
    flex-wrap: nowrap;
    scrollbar-width: thin;
    -webkit-overflow-scrolling: touch;
  }
  .cat-tab {
    flex: 0 0 auto;
    height: var(--h-mobile);
  }
}

@media (max-width: 639px) {
  .cat-tab {
    height: var(--h-mobile);
  }
}
</style>
