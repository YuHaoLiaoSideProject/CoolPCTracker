<script setup lang="ts">
// web/src/components/PriceTrendChart.vue — lightweight-charts 歷史趨勢圖（開發規格 004 §2.5 / UIUX §4.4）
// 純 props → 圖表渲染，不持有跨元件狀態。要點：
//   - time 用 "yyyy-mm-dd" 字串（非等間距如實呈現，不補點，E14）
//   - tooltip 自寫 DOM（subscribeCrosshairMove：日期＋價格＋目標價，定位/clamp/離開隱藏）
//   - 縮放平移：lwc 內建滾輪縮放＋拖曳平移；雙擊重置 → timeScale().fitContent()
//   - 目標價：series.createPriceLine（dashed #f59e0b，價格軸 title「目標價」）
//   - 單筆降級（E5）：circle marker＋價格文字、X 軸居中 setVisibleLogicalRange({from:-1.5,to:1.5})
//   - ResizeObserver applyOptions({width,height}) + onUnmounted 清理；容器 0 寬時延後 init（E16）
//   - 無障礙：容器 role="img"＋aria-label（WCAG A5）
import { computed, onMounted, onUnmounted, ref, watch } from "vue"
import {
  createChart,
  createSeriesMarkers,
  LineSeries,
  LineType,
} from "@/lib/lightweight-charts"
import type {
  IChartApi,
  ISeriesApi,
  ISeriesMarkersPluginApi,
  IPriceLine,
  LineData,
  MouseEventParams,
  Time,
} from "@/lib/lightweight-charts"
import type { PricePoint } from "@/types/item"
import { formatNumber } from "@/utils/format"
import {
  BRAND_COLOR,
  buildChartOptions,
  buildMarkers,
  buildPriceLineOptions,
  buildSeriesData,
  computeTooltipPosition,
  formatChartDate,
} from "@/lib/priceTrend"

const props = defineProps<{
  history: PricePoint[] // 依 d 升冪；長度 ≥1（空歷史由 view 降級，不渲染本元件）
  targetPrice?: number | null // null/undefined = 不顯示目標價線
  yMin?: number // Y 軸下限（view 含目標價擴展後傳入；lwc 自動縮放，此值保留契約相容）
  yMax?: number
}>()

const CHART_HEIGHT = 360
const TOOLTIP_EST_WIDTH = 150
const TOOLTIP_EST_HEIGHT = 72

interface TooltipState {
  date: string
  price: string
  target: string | null
  left: number
  top: number
}

const el = ref<HTMLDivElement | null>(null)
const tooltipEl = ref<HTMLDivElement | null>(null)
const tooltip = ref<TooltipState | null>(null)

let chart: IChartApi | null = null
let series: ISeriesApi<"Line", Time> | null = null
let markersApi: ISeriesMarkersPluginApi<Time> | null = null
let priceLine: IPriceLine | null = null
let observer: ResizeObserver | null = null

const tooltipStyle = computed(() => {
  const t = tooltip.value
  return t ? { left: `${t.left}px`, top: `${t.top}px` } : {}
})

function applyTargetLine(): void {
  if (!series) return
  if (priceLine) {
    series.removePriceLine(priceLine)
    priceLine = null
  }
  if (props.targetPrice != null) {
    priceLine = series.createPriceLine(buildPriceLineOptions(props.targetPrice))
  }
}

function render(): void {
  if (!chart || !series) return
  series.setData(buildSeriesData(props.history))
  markersApi?.setMarkers(buildMarkers(props.history))
  applyTargetLine()
  if (props.history.length === 1) {
    chart.timeScale().setVisibleLogicalRange({ from: -1.5, to: 1.5 })
  }
}

function onCrosshairMove(param: MouseEventParams<Time>): void {
  if (!param.point || param.time == null) {
    tooltip.value = null
    return
  }
  const data = param.seriesData.get(series as ISeriesApi<"Line", Time>) as LineData<Time> | undefined
  const value = data?.value
  if (value == null) {
    tooltip.value = null
    return
  }
  const pos = computeTooltipPosition(
    { x: param.point.x, y: param.point.y },
    { width: el.value?.clientWidth ?? 0, height: el.value?.clientHeight ?? CHART_HEIGHT },
    {
      width: tooltipEl.value?.offsetWidth || TOOLTIP_EST_WIDTH,
      height: tooltipEl.value?.offsetHeight || TOOLTIP_EST_HEIGHT,
    },
  )
  tooltip.value = {
    date: formatChartDate(param.time),
    price: formatNumber(value),
    target: props.targetPrice != null ? formatNumber(props.targetPrice) : null,
    left: pos.left,
    top: pos.top,
  }
}

function onDoubleClick(): void {
  chart?.timeScale().fitContent()
}

function initChart(): void {
  if (chart || !el.value || el.value.clientWidth === 0) return // E16：0 寬容器延後 init
  const width = el.value.clientWidth
  const height = el.value.clientHeight || CHART_HEIGHT
  chart = createChart(el.value, buildChartOptions({ width, height }))
  series = chart.addSeries(LineSeries, {
    color: BRAND_COLOR,
    lineWidth: 2,
    lineType: LineType.Simple,
    priceLineVisible: false,
    lastValueVisible: false,
  })
  series.setData(buildSeriesData(props.history))
  markersApi = createSeriesMarkers(series, buildMarkers(props.history))
  applyTargetLine()
  if (props.history.length === 1) {
    chart.timeScale().setVisibleLogicalRange({ from: -1.5, to: 1.5 })
  }
  chart.subscribeCrosshairMove(onCrosshairMove)
  chart.subscribeDblClick(onDoubleClick)
}

onMounted(() => {
  initChart()
  observer = new ResizeObserver(() => {
    if (!chart && el.value && el.value.clientWidth > 0) initChart()
    else if (chart && el.value) {
      chart.applyOptions({
        width: el.value.clientWidth,
        height: el.value.clientHeight || CHART_HEIGHT,
      })
    }
  })
  observer.observe(el.value as HTMLDivElement)
})

watch(
  () => [props.history, props.targetPrice, props.yMin, props.yMax],
  () => render(),
  { deep: true },
)

onUnmounted(() => {
  observer?.disconnect()
  observer = null
  if (chart) {
    chart.unsubscribeCrosshairMove(onCrosshairMove)
    chart.unsubscribeDblClick(onDoubleClick)
    markersApi?.detach()
  }
  markersApi = null
  priceLine = null
  chart?.remove()
  chart = null
  series = null
  tooltip.value = null
})
</script>

<template>
  <div class="price-trend-chart-wrap">
    <div ref="el" class="price-trend-chart" role="img" aria-label="歷史價格趨勢圖" />
    <div v-if="tooltip" ref="tooltipEl" class="chart-tooltip" :style="tooltipStyle">
      <div class="tt-date">{{ tooltip.date }}</div>
      <div class="tt-price">價格：NT${{ tooltip.price }}</div>
      <div v-if="tooltip.target != null" class="tt-target">目標價 NT${{ tooltip.target }}</div>
    </div>
  </div>
</template>

<style scoped>
.price-trend-chart-wrap {
  position: relative;
  width: 100%;
}

.price-trend-chart {
  width: 100%;
  height: 360px;
}

.chart-tooltip {
  position: absolute;
  z-index: 5;
  pointer-events: none;
  min-width: 132px;
  padding: 8px 10px;
  border-radius: 6px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  font-size: 12px;
  line-height: 1.6;
  color: #1f2937;
  white-space: nowrap;
}

.tt-date {
  font-weight: 600;
  margin-bottom: 2px;
}

.tt-price {
  color: #1f2937;
}

.tt-target {
  color: #92400e;
}
</style>
