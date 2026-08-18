<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'
import { useCompare } from '@/composables/useCompare'

const props = defineProps<{
  id: string
  category: string
  variant?: 'checkbox' | 'button'
}>()

const { isSelected, isFull, toggle } = useCompare()

const toast = ref('')
let timer: ReturnType<typeof setTimeout> | null = null

function showToast(msg: string) {
  if (timer) clearTimeout(timer)
  toast.value = msg
  timer = setTimeout(() => { toast.value = '' }, 2000)
}

onBeforeUnmount(() => { if (timer) clearTimeout(timer) })

const checked = computed(() => isSelected(props.id))
const variant = computed(() => props.variant ?? 'checkbox')
const disabled = computed(() => isFull.value && !checked.value)

function handleClick() {
  if (disabled.value) {
    showToast('最多只能比較 6 件商品')
    return
  }

  const result = toggle({ id: props.id, category: props.category })

  if ('ok' in result && !result.ok) {
    switch (result.reason) {
      case 'different-category':
        showToast(result.message)
        break
      case 'max-6':
        showToast(result.message)
        break
    }
  }
}
</script>

<template>
  <span class="compare-toggle-wrap">
    <label
      v-if="variant === 'checkbox'"
      class="compare-toggle"
      :class="{ checked, disabled }"
    >
      <input
        type="checkbox"
        class="sr-only"
        :checked="checked"
        :disabled="disabled"
        @change="handleClick"
      />
      <span class="compare-checkbox" aria-hidden="true">
        <svg v-if="checked" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </span>
      <span class="compare-label">{{ checked ? '已加入比價' : '加入比價' }}</span>
    </label>

    <button
      v-else
      type="button"
      class="compare-toggle-btn"
      :class="{ checked, disabled }"
      :disabled="disabled"
      :aria-pressed="checked"
      :title="checked ? '取消比價' : '加入比價'"
      @click="handleClick"
    >
      <svg v-if="checked" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="20 6 9 17 4 12" />
      </svg>
      <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="12" y1="5" x2="12" y2="19" />
        <line x1="5" y1="12" x2="19" y2="12" />
      </svg>
      <span>{{ checked ? '已加入' : '加入比價' }}</span>
    </button>

    <Transition name="toast-fade">
      <span v-if="toast" class="compare-toast" role="status">{{ toast }}</span>
    </Transition>
  </span>
</template>

<style scoped>
.compare-toggle-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
}

/* ---- checkbox variant ---- */
.compare-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.4em;
  cursor: pointer;
  font-size: 0.85rem;
  user-select: none;
}

.compare-toggle.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.compare-checkbox {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: 2px solid var(--border, #aaa);
  border-radius: 4px;
  background: var(--btn-bg, #fff);
  transition: background 0.2s, border-color 0.2s;
}

.compare-toggle.checked .compare-checkbox {
  background: var(--accent, #4a9eff);
  border-color: var(--accent, #4a9eff);
  color: #fff;
}

.compare-label {
  color: var(--text, #333);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* ---- button variant ---- */
.compare-toggle-btn {
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

.compare-toggle-btn:hover:not(:disabled) {
  background: var(--btn-hover-bg, #f0f0f0);
}

.compare-toggle-btn.checked {
  background: var(--accent, #4a9eff);
  color: #fff;
  border-color: var(--accent, #4a9eff);
}

.compare-toggle-btn.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* toast */
.compare-toast {
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
