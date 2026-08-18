<!-- web/src/components/DashboardSkeleton.vue — 全頁骨架屏（開發規格 017 §2.4）-->
<!-- Tab 區域（5 個 tab 佔位）+ 列表區域（10 個卡片佔位）+ shimmer 動畫 -->
<template>
  <div class="dashboard-skeleton" aria-hidden="true">
    <div class="ds-tabs">
      <div v-for="i in 5" :key="i" class="ds-tab shimmer" />
    </div>
    <div class="ds-list">
      <div v-for="i in 10" :key="i" class="ds-card shimmer" />
    </div>
  </div>
</template>

<style scoped>
.dashboard-skeleton {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ds-tabs {
  display: flex;
  gap: 8px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}

.ds-tab {
  width: 80px;
  height: 32px;
  border-radius: var(--radius-sm);
}

.ds-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.ds-card {
  height: 120px;
  border-radius: var(--radius);
}

.shimmer {
  background: linear-gradient(90deg, var(--surface) 25%, var(--surface-2) 50%, var(--surface) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

@media (max-width: 639px) {
  .ds-list {
    grid-template-columns: 1fr;
  }
}
</style>
