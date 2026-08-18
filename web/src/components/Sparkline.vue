<script setup lang="ts">
// web/src/components/Sparkline.vue — SVG 迷你趨勢圖（開發規格 003 §2.10）
// viewBox 0 0 100 28 polyline；history < 2 筆不畫線，顯示「資料不足」。
// Phase 20：新增 trend 動態著色 + enableTooltip hover tooltip。
import { computed, ref } from "vue"
import type { PricePoint } from "@/types/item"
import type { PriceTrend } from "@/lib/priceChange"
import SparklineTooltip from "./SparklineTooltip.vue"

const props = withDefaults(defineProps<{
  points: PricePoint[]
  trend?: PriceTrend | null
  enableTooltip?: boolean
}>(), {
  trend: null,
  enableTooltip: false,
})

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

// ── tooltip hover ──
const hoveredIndex = ref<number | null>(null)
const hoveredX = ref<number>(0)

function onMouseMove(e: MouseEvent) {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const xPercent = ((e.clientX - rect.left) / rect.width) * 100
  hoveredX.value = xPercent
  hoveredIndex.value = Math.round((xPercent / 100) * (props.points.length - 1))
}

function onMouseLeave() {
  hoveredIndex.value = null
}

// ── trend → CSS class ──
const trendClass = computed(() => {
  switch (props.trend) {
    case "up": return "sparkline--up"
    case "down": return "sparkline--down"
    case "flat": return "sparkline--flat"
    default: return ""
  }
})
</script>

<template>
  <div class="sparkline-container">
    <svg
      v-if="props.points.length >= 2"
      :class="['sparkline', trendClass]"
      viewBox="0 0 100 28"
      preserveAspectRatio="none"
      aria-hidden="true"
      @mousemove="enableTooltip ? onMouseMove($event) : undefined"
      @mouseleave="enableTooltip ? onMouseLeave() : undefined"
    >
      <polyline :points="poly" />
    </svg>
    <span v-else class="sparkline--empty">資料不足</span>
    <SparklineTooltip
      v-if="enableTooltip && hoveredIndex !== null && points[hoveredIndex]"
      :point="points[hoveredIndex]"
      :x="hoveredX"
    />
  </div>
</template>

<style scoped>
.sparkline-container {
  position: relative;
  display: inline-block;
  width: 100%;
}

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

.sparkline--up polyline {
  stroke: var(--price-up);
}

.sparkline--down polyline {
  stroke: var(--price-down);
}

.sparkline--flat polyline {
  stroke: var(--price-flat);
}

.sparkline--empty {
  display: block;
  height: 28px;
  line-height: 28px;
  color: var(--text-dim);
  font-size: 0.8rem;
}
</style>
