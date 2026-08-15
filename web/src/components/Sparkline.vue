<script setup lang="ts">
// web/src/components/Sparkline.vue — SVG 迷你趨勢圖（開發規格 003 §2.10）
// viewBox 0 0 100 28 polyline；history < 2 筆不畫線，顯示「—」
// （與 005 追蹤頁「資料不足」語意一致）。
import { computed } from "vue"
import type { PricePoint } from "@/types/item"

const props = defineProps<{ points: PricePoint[] }>()

const W = 100
const H = 28
const PAD = 2

/** 將 history 縮放至 100×28 座標系，回傳 "x1,y1 x2,y2 …" */
const poly = computed(() => {
  const pts = props.points
  if (pts.length < 2) return ""
  const prices = pts.map(p => p.p)
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const span = max - min || 1
  const x = (i: number) => (i / (pts.length - 1)) * W
  const y = (p: number) => H - PAD - ((p - min) / span) * (H - PAD * 2)
  return pts.map((pt, i) => `${x(i).toFixed(1)},${y(pt.p).toFixed(1)}`).join(" ")
})
</script>

<template>
  <svg
    v-if="props.points.length >= 2"
    class="sparkline"
    viewBox="0 0 100 28"
    preserveAspectRatio="none"
    aria-hidden="true"
  >
    <polyline :points="poly" />
  </svg>
  <span v-else class="sparkline--empty">—</span>
</template>

<style scoped>
.sparkline {
  width: 100%;
  height: 28px;
  display: block;
}

.sparkline polyline {
  fill: none;
  stroke: var(--brand);
  stroke-width: 1.5;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.sparkline--empty {
  display: block;
  height: 28px;
  line-height: 28px;
  color: var(--text-dim);
  font-size: 0.8rem;
}
</style>
