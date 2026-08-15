<script setup lang="ts">
// web/src/components/ErrorState.vue — 錯誤狀態（開發規格 003 §2.11 / §6.1）
// fetch 失敗 →「資料載入失敗」；parse 失敗 →「資料格式錯誤」；皆附「重試」。
// 錯誤只在列表區域呈現（側欄／搜尋／篩選照常渲染，不白屏）。
defineProps<{ kind: "fetch" | "parse" }>()

const emit = defineEmits<{ (e: "retry"): void }>()

const copy = {
  fetch: {
    title: "資料載入失敗",
    desc: "無法取得商品資料（網路中斷或資料檔暫時不可得）。",
  },
  parse: {
    title: "資料格式錯誤",
    desc: "資料檔案內容異常，可能尚未完成更新或檔案損毀。",
  },
}
</script>

<template>
  <div class="error-state" role="alert">
    <span class="es-ico" aria-hidden="true">
      <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 8v4M12 16h.01" />
      </svg>
    </span>
    <h3>{{ copy[kind].title }}</h3>
    <p>{{ copy[kind].desc }}</p>
    <button type="button" class="retry-btn" @click="emit('retry')">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M23 4v6h-6M1 20v-6h6" />
        <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
      </svg>
      <span>重試</span>
    </button>
  </div>
</template>

<style scoped>
.error-state {
  text-align: center;
  padding: 48px 16px;
  color: var(--text-dim);
}

.es-ico {
  display: inline-flex;
  margin-bottom: 12px;
  color: var(--danger);
}

.error-state h3 {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 6px;
}

.error-state p {
  font-size: 0.85rem;
  max-width: 380px;
  margin: 0 auto;
}

.retry-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: var(--h);
  padding: 0 18px;
  margin-top: 18px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--brand);
  color: #fff;
  font-size: 0.86rem;
  font-weight: 600;
  transition: filter var(--transition);
}

.retry-btn:hover {
  filter: brightness(1.05);
}

@media (max-width: 639px) {
  .retry-btn {
    height: var(--h-mobile);
  }
}
</style>
