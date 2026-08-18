<!-- web/src/components/SparklineTooltip.vue — Sparkline hover tooltip 子元件（開發規格 020 §2.3）-->
<script setup lang="ts">
import type { PricePoint } from "@/types/item"
import { formatPrice } from "@/utils/format"

defineProps<{
  point: PricePoint
  x: number
}>()
</script>

<template>
  <div
    class="sparkline-tooltip"
    :style="{ left: `${x}%`, transform: 'translateX(-50%)' }"
  >
    <span class="sparkline-tooltip__date">{{ point.d }}</span>
    <span class="sparkline-tooltip__price">NT${{ formatPrice(point.p) }}</span>
  </div>
</template>

<style scoped>
.sparkline-tooltip {
  position: absolute;
  bottom: 100%;
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  font-size: 0.72rem;
  white-space: nowrap;
  pointer-events: none;
  z-index: 10;
}

.sparkline-tooltip__date {
  color: var(--text-secondary);
  margin-right: 4px;
}

.sparkline-tooltip__price {
  color: var(--text-primary);
  font-weight: 500;
}
</style>
