<script setup lang="ts">
// web/src/components/SearchBar.vue — 搜尋框（開發規格 003 §2.8）
// 受控輸入 + 300ms debounce；外部清空（clearAll）需同步 input 值。
// 僅空白字元輸入在過濾層自然為 no-op（§6.3）。
import { onUnmounted, ref, watch } from "vue"

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ (e: "update:modelValue", v: string): void }>()

const input = ref(props.modelValue)
let timer: ReturnType<typeof setTimeout> | undefined

watch(input, v => {
  clearTimeout(timer)
  timer = setTimeout(() => emit("update:modelValue", v), 300) // debounce
})
watch(() => props.modelValue, v => {
  if (v !== input.value) {
    clearTimeout(timer) // 外部清空（clearAll）時取消 pending debounce，避免關鍵字復活
    input.value = v // 外部清空同步
  }
})

onUnmounted(() => clearTimeout(timer)) // 離開頁面時清掉 pending timer（避免 unmount 後 emit）

function clear() {
  input.value = ""
}
</script>

<template>
  <div class="search" :class="{ 'has-value': input !== '' }">
    <span class="s-ico" aria-hidden="true">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="7" />
        <path d="M21 21l-4.3-4.3" />
      </svg>
    </span>
    <input
      v-model="input"
      type="search"
      class="search-input"
      placeholder="搜尋商品名稱或規格…"
      aria-label="搜尋商品名稱或規格"
      autocomplete="off"
    />
    <button
      v-if="input !== ''"
      class="s-clear"
      type="button"
      aria-label="清除搜尋"
      @click="clear"
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true">
        <path d="M18 6L6 18M6 6l12 12" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.search {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  height: var(--h);
  max-width: 400px;
  width: 100%;
  padding: 0 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  transition: border-color var(--transition), box-shadow var(--transition);
}

.search:focus-within {
  border-color: var(--accent);
  box-shadow: var(--focus-ring);
}

.s-ico {
  display: inline-flex;
  color: var(--text-dim);
  flex: 0 0 auto;
}

.search-input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--fs);
}

.search-input::placeholder {
  color: var(--text-dim);
}

.s-clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--text-dim);
  transition: background-color var(--transition), color var(--transition);
}

.s-clear:hover {
  background: var(--border);
  color: var(--text);
}

/* 手機：全寬、控制高度 44px */
@media (max-width: 639px) {
  .search {
    max-width: none;
    height: var(--h-mobile);
  }
}
</style>
