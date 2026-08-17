<script setup lang="ts">
// web/src/components/CategorySidebar.vue — 分類側欄（契約 v2：資料驅動）
// 渲染「全部」＋ index.json categories[] 全部分類、高亮目前分類、顯示各分類商品數
// （count 直接來自 index 統計 — lazy 載入下 items 未全載時側欄數字才正確）。
// 不直接操作 URL／資料——透過 select 事件交給 ListingView 統一處理（loadCategory/loadAll + router）。
import type { CategoryMeta } from "@/types/item"

defineProps<{
  categories: CategoryMeta[] // 由 useItems 提供（index.json 目錄）
  active: string | null // 目前選中分類 id；null = 全部
  total: number // 「全部」的總筆數（index counts 加總）
}>()

const emit = defineEmits<{
  (e: "select", id: string | null): void // null = 全部（→ ListingView 呼叫 loadAll）
}>()
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
        <span class="cat-cnt" aria-hidden="true">{{ total }}</span>
      </button>
      <button
        v-for="c in categories"
        :key="c.id"
        type="button"
        class="cat"
        :class="{ 'is-active': active === c.id }"
        :aria-pressed="active === c.id"
        @click="emit('select', c.id)"
      >
        <span>{{ c.name }}</span>
        <span class="cat-cnt" aria-hidden="true">{{ c.count }}</span>
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