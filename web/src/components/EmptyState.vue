<script setup lang="ts">
// web/src/components/EmptyState.vue — 空狀態三分流（開發規格 003 §2.11 / §6.2）
// 分流優先序：keyword 有值 → search；conditions 有值 → filter；其餘 → category。
// 空分類 = 純說明不報錯、不觸發重試。
defineProps<{
  kind: "search" | "filter" | "category"
  keyword?: string // kind='search'：顯示「沒有符合『{keyword}』的商品」
  conditions?: string[] // kind='filter'：列出已套用條件
}>()

const emit = defineEmits<{ (e: "clear"): void }>()

const copy = {
  search: {
    title: (k?: string) => (k ? `沒有符合「${k}」的商品` : "沒有符合條件的商品"),
    desc: "搜尋範圍僅涵蓋商品名稱與規格欄位，試試其他關鍵字。",
    action: "清除搜尋",
  },
  filter: {
    title: () => "沒有符合條件的商品",
    desc: "試著放寬或移除部分篩選條件。",
    action: "清除篩選",
  },
  category: {
    title: () => "此分類目前沒有商品",
    desc: "資料可能尚未收錄此分類的商品，或該分類當日為 0 筆。",
    action: "查看全部商品",
  },
}
</script>

<template>
  <div class="empty-state">
    <span class="es-ico" aria-hidden="true">
      <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="7" />
        <path d="M21 21l-4.3-4.3M8.5 8.5l5 5M13.5 8.5l-5 5" />
      </svg>
    </span>
    <h3>{{ copy[kind].title(keyword) }}</h3>
    <p>{{ copy[kind].desc }}</p>
    <div v-if="kind === 'filter' && conditions?.length" class="empty-conds">
      <span v-for="c in conditions" :key="c" class="fchip">{{ c }}</span>
    </div>
    <div class="empty-actions">
      <button type="button" class="btn" @click="emit('clear')">{{ copy[kind].action }}</button>
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  text-align: center;
  padding: 48px 16px;
  color: var(--text-dim);
}

.es-ico {
  display: inline-flex;
  margin-bottom: 12px;
  color: var(--text-dim);
}

.empty-state h3 {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 6px;
}

.empty-state p {
  font-size: 0.85rem;
  max-width: 380px;
  margin: 0 auto;
}

.empty-conds {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px;
  margin-top: 14px;
}

.fchip {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 0.8rem;
  font-weight: 600;
}

.empty-actions {
  margin-top: 18px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: var(--h);
  padding: 0 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font-size: 0.86rem;
  font-weight: 600;
  transition: background-color var(--transition), border-color var(--transition);
}

.btn:hover {
  border-color: var(--brand);
  color: var(--brand);
}

@media (max-width: 639px) {
  .btn {
    height: var(--h-mobile);
  }
}
</style>
