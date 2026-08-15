<script setup lang="ts">
// web/src/components/CategorySidebar.vue — 分類側欄（開發規格 003 §2.7）
// 渲染 9 大分類（含「全部」）、高亮目前分類、顯示各分類商品數。
// 不直接操作 URL——透過 select 事件交給 ListingView 統一同步 router。
import { CATEGORIES, type CategoryKey } from "@/data/categories"

defineProps<{
  active: CategoryKey | null // 目前分類；null = 全部
  counts?: Record<string, number> // 分類中文標籤 → 商品數（由 ListingView 計算傳入）
}>()

const emit = defineEmits<{
  (e: "select", key: CategoryKey | null): void // null = 全部
}>()

const total = (counts: Record<string, number> | undefined): number =>
  counts ? Object.values(counts).reduce((a, b) => a + b, 0) : 0
</script>

<template>
  <nav class="sidebar" aria-label="商品分類">
    <div class="sidebar-title">分類</div>
    <div class="sidebar-list">
      <button
        type="button"
        class="cat"
        :class="{ 'is-active': active === null }"
        :aria-pressed="active === null"
        @click="emit('select', null)"
      >
        <span>全部</span>
        <span class="cat-cnt" aria-hidden="true">{{ total(counts) }}</span>
      </button>
      <button
        v-for="c in CATEGORIES"
        :key="c.key"
        type="button"
        class="cat"
        :class="{ 'is-active': active === c.key }"
        :aria-pressed="active === c.key"
        @click="emit('select', c.key)"
      >
        <span>{{ c.label }}</span>
        <span class="cat-cnt" aria-hidden="true">{{ counts?.[c.label] ?? 0 }}</span>
      </button>
    </div>
  </nav>
</template>

<style scoped>
.sidebar-title {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-dim);
  padding: 0 6px 8px;
}

.sidebar-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cat {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  height: var(--h);
  padding: 0 10px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text);
  font-size: 0.88rem;
  text-align: left;
  transition: background-color var(--transition), color var(--transition),
    border-color var(--transition);
}

.cat:hover {
  background: var(--brand-soft);
}

.cat.is-active {
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 700;
  border-color: var(--brand);
}

.cat-cnt {
  font-size: 0.75rem;
  color: var(--text-dim);
  background: var(--surface-2);
  border-radius: 999px;
  padding: 1px 8px;
  font-variant-numeric: tabular-nums;
}

.cat.is-active .cat-cnt {
  background: var(--surface);
}

/* 平板（≤1023px）：側欄收合為頂部水平捲動 chips（開發規格 §7.6） */
@media (max-width: 1023px) {
  .sidebar-title {
    display: none;
  }

  .sidebar-list {
    flex-direction: row;
    overflow-x: auto;
    gap: 8px;
    padding-bottom: 4px;
    scrollbar-width: thin;
  }

  .cat {
    flex: 0 0 auto;
    width: auto;
    justify-content: flex-start;
  }
}

/* 手機（≤639px）：觸控目標 44px（WCAG 2.5.5，UIUX §5） */
@media (max-width: 639px) {
  .cat {
    height: var(--h-mobile);
  }
}
</style>
