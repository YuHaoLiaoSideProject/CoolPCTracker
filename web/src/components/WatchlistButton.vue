<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'
import { useWatchlist } from '@/composables/useWatchlist'

const props = defineProps<{
  id: string
  price: number | null
  variant?: 'button' | 'icon'
}>()

const { isTracked, add, remove } = useWatchlist()

const toast = ref('')
let timer: ReturnType<typeof setTimeout> | null = null

function showToast(msg: string) {
  if (timer) clearTimeout(timer)
  toast.value = msg
  timer = setTimeout(() => { toast.value = '' }, 2000)
}

onBeforeUnmount(() => { if (timer) clearTimeout(timer) })

const tracked = computed(() => isTracked(props.id))
const variant = computed(() => props.variant ?? 'button')

function handleClick() {
  if (tracked.value) {
    remove(props.id)
    return
  }

  if (props.price === null) {
    showToast('該商品目前無價格，無法追蹤')
    return
  }

  const result = add(props.id, props.price)
  if (!result.ok) {
    switch (result.reason) {
      case 'already-tracked':
        showToast('該商品已在追蹤清單')
        break
      case 'storage-unavailable':
        showToast('瀏覽器未開放本機儲存，無法使用追蹤功能')
        break
      case 'quota-exceeded':
        showToast('儲存空間已滿，無法新增追蹤項目')
        break
    }
    return
  }

  showToast('已加入追蹤')
}
</script>

<template>
  <span class="watchlist-btn-wrap">
    <button
      type="button"
      class="watchlist-btn"
      :class="{ tracked, 'is-icon': variant === 'icon' }"
      :aria-pressed="tracked"
      :title="tracked ? '取消追蹤' : '加入追蹤'"
      @click="handleClick"
    >
      <!-- icon: star -->
      <svg v-if="tracked" width="15" height="15" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
      </svg>
      <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
      </svg>
      <span v-if="variant !== 'icon'">{{ tracked ? '已追蹤' : '加入追蹤' }}</span>
    </button>
    <Transition name="toast-fade">
      <span v-if="toast" class="watchlist-toast" role="status">{{ toast }}</span>
    </Transition>
  </span>
</template>

<style scoped>
.watchlist-btn-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.watchlist-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35em;
  padding: 0.4em 0.85em;
  border: 1px solid var(--border, #ccc);
  border-radius: 6px;
  background: var(--btn-bg, #fff);
  color: var(--text, #333);
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, border-color 0.2s;
  white-space: nowrap;
}

.watchlist-btn:hover {
  background: var(--btn-hover-bg, #f0f0f0);
}

.watchlist-btn.tracked {
  background: var(--accent, #f5a623);
  color: #fff;
  border-color: var(--accent, #f5a623);
}

.watchlist-btn.tracked:hover {
  background: var(--accent-hover, #e09510);
}

.watchlist-btn.is-icon {
  padding: 0.35em;
  border: none;
  background: transparent;
}

.watchlist-btn.is-icon:hover {
  background: var(--btn-hover-bg, #f0f0f0);
}

.watchlist-btn.is-icon.tracked {
  background: transparent;
  color: var(--accent, #f5a623);
}

/* toast */
.watchlist-toast {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  padding: 0.3em 0.7em;
  border-radius: 4px;
  background: var(--toast-bg, #333);
  color: var(--toast-color, #fff);
  font-size: 0.78rem;
  white-space: nowrap;
  pointer-events: none;
  z-index: 20;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.3s;
}
.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
}
</style>
