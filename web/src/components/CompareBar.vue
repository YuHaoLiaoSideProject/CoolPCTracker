<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useCompare } from '@/composables/useCompare'

const router = useRouter()
const { count, canStart, clear } = useCompare()

function goToCompare() {
  router.push('/compare')
}
</script>

<template>
  <Transition name="bar-slide">
    <div v-if="count > 0" class="compare-bar">
      <div class="compare-bar-inner">
        <span class="compare-bar-count">已選 <strong>{{ count }}</strong> / 6</span>
        <div class="compare-bar-actions">
          <button
            type="button"
            class="compare-bar-btn clear"
            @click="clear"
          >
            清除比價
          </button>
          <button
            type="button"
            class="compare-bar-btn primary"
            :disabled="!canStart"
            :title="canStart ? '開始比價' : '請至少選擇 2 件商品進行比價'"
            @click="goToCompare"
          >
            開始比價
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.compare-bar {
  position: sticky;
  bottom: 0;
  z-index: 10;
  background: var(--compare-bar-bg, #fff);
  border-top: 1px solid var(--border, #ddd);
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.08);
}

.compare-bar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0.6rem 1rem;
}

.compare-bar-count {
  font-size: 0.9rem;
  color: var(--text, #333);
}

.compare-bar-count strong {
  color: var(--accent, #4a9eff);
}

.compare-bar-actions {
  display: flex;
  gap: 0.5rem;
}

.compare-bar-btn {
  padding: 0.45em 1em;
  border: 1px solid var(--border, #ccc);
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.compare-bar-btn.clear {
  background: transparent;
  color: var(--text-secondary, #666);
  border-color: var(--border, #ccc);
}

.compare-bar-btn.clear:hover {
  background: var(--btn-hover-bg, #f0f0f0);
}

.compare-bar-btn.primary {
  background: var(--accent, #4a9eff);
  color: #fff;
  border-color: var(--accent, #4a9eff);
}

.compare-bar-btn.primary:hover:not(:disabled) {
  background: var(--accent-hover, #3580e0);
}

.compare-bar-btn.primary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* slide transition */
.bar-slide-enter-active,
.bar-slide-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}
.bar-slide-enter-from,
.bar-slide-leave-to {
  transform: translateY(100%);
  opacity: 0;
}
</style>
