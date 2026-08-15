<script setup lang="ts">
// web/src/components/WatchActions.vue — 追蹤／比價動作區（開發規格 004 §2.1 / §8 step 9，005 預留佔位）
// 004 僅渲染佔位並接收 item.id；005 實作時改為 emit toggle-watch / toggle-compare 並接 store。
defineProps<{ itemId: string }>()
</script>

<template>
  <section class="watch-actions" aria-label="追蹤與比價">
    <p class="wa-note">追蹤與比價功能將於下一階段（005）開放。</p>
    <div class="wa-buttons">
      <!-- 005：改為可互動按鈕（emit toggle-watch / toggle-compare），itemId 已備妥 -->
      <button type="button" class="wa-btn" disabled>加入追蹤</button>
      <button type="button" class="wa-btn" disabled>加入比價</button>
    </div>
  </section>
</template>

<style scoped>
.watch-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  box-shadow: var(--shadow);
}

.wa-note {
  font-size: 13px;
  color: var(--text-dim);
}

.wa-buttons {
  display: flex;
  gap: 8px;
}

.wa-btn {
  height: var(--h);
  padding: 0 16px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text-dim);
  font-size: 0.85rem;
  font-weight: 600;
  opacity: 0.65;
}

@media (max-width: 639px) {
  .watch-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .wa-buttons {
    flex-direction: column;
  }

  .wa-btn {
    height: var(--h-mobile);
  }
}
</style>
