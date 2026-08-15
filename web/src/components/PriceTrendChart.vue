<script setup lang="ts">
// web/src/components/PriceTrendChart.vue — ECharts 歷史趨勢圖（開發規格 004 §2.5 / UIUX §4.4）
// 純 props → option 渲染，不持有跨元件狀態。要點：
//   - xAxis type 'time'：非等間距如實呈現（不補點，E14）
//   - tooltip 懸停（日期＋價格＋目標價）、dataZoom inside +（點數 ≥15 顯示 slider）
//   - markLine 目標價：dashed #f59e0b、silent、label「目標價 NT$9,500」（§7 琥珀期望線語意）
//   - 單筆降級：symbolSize 放大＋label 顯示價格、停用 dataZoom、X 軸以該日為中心（E5）
//   - ResizeObserver resize + onUnmounted dispose；容器 0 寬時延後 init（E16）
//   - 無障礙：容器 role="img"＋aria-label（WCAG A5）
import { onMounted, onUnmounted, ref, watch } from "vue"
import type { ECharts } from "echarts/core"
import type { EChartsOption } from "@/lib/echarts"
import echarts from "@/lib/echarts"
import type { PricePoint } from "@/types/item"
import { formatNumber } from "@/utils/format"

const props = defineProps<{
  history: PricePoint[] // 依 d 升冪；長度 ≥1（空歷史由 view 降級，不渲染本元件）
  targetPrice?: number | null // null/undefined = 不顯示 markLine
  yMin?: number // Y 軸下限（view 含目標價擴展後傳入）
  yMax?: number
}>()

// Canvas renderer 不吃 CSS var()，直接取 design token 值（tokens.css，兩主題共用色調）
const MARK_LINE_COLOR = "#f59e0b" // 琥珀期望線（UIUX §3.1 --warning 對應色）
const BRAND_COLOR = "#1f6feb"
const SLIDER_BG = "#f1f3f5"
const SLIDER_FILL = "rgba(31, 111, 235, 0.12)"

const el = ref<HTMLDivElement | null>(null)
let chart: ECharts | null = null
let observer: ResizeObserver | null = null

const pad2 = (n: number): string => String(n).padStart(2, "0")

function reduceMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  )
}

function buildOption(): EChartsOption {
  const points = props.history.map((h) => [h.d, h.p])
  const single = props.history.length === 1
  const hasTarget = props.targetPrice != null

  const option: EChartsOption = {
    animation: !reduceMotion(),
    grid: { left: 10, right: 18, top: 40, bottom: single ? 30 : 52, containLabel: true },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      formatter: (params: any): string => {
        const list = Array.isArray(params) ? params : [params]
        const p = list[0]
        if (!p) return ""
        const date = new Date(p.value[0])
        const dateStr = `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`
        const price = `NT$${formatNumber(p.value[1])}`
        const target = hasTarget ? `<br/>目標價 NT$${formatNumber(props.targetPrice as number)}` : ""
        return `${dateStr}<br/>價格：${price}${target}`
      },
    },
    xAxis: {
      type: "time",
      axisLabel: {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        formatter: (v: any): string => {
          const d = new Date(v)
          return `${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
        },
      },
      ...(single
        ? (() => {
            // 單筆：以該日為中心 ±12h 視窗
            const t = new Date(points[0][0] as string).getTime()
            const half = 12 * 3600 * 1000
            return { min: t - half, max: t + half }
          })()
        : {}),
    },
    yAxis: {
      type: "value",
      min: props.yMin,
      max: props.yMax,
      scale: true,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      axisLabel: { formatter: (v: any): string => `NT$${formatNumber(v)}` },
    },
    dataZoom: single
      ? []
      : [
          { type: "inside" },
          {
            type: "slider",
            show: props.history.length >= 15, // 點數 ≥15 才顯示 slider
            height: 14,
            bottom: 6,
            borderColor: "transparent",
            backgroundColor: SLIDER_BG,
            fillerColor: SLIDER_FILL,
          },
        ],
    series: [
      {
        type: "line",
        data: points,
        smooth: false,
        showSymbol: single || points.length <= 24,
        symbol: "circle",
        symbolSize: single ? 10 : 6,
        lineStyle: { width: 2, color: BRAND_COLOR },
        itemStyle: { color: BRAND_COLOR },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        label: single ? { show: true, formatter: (p: any): string => `NT$${formatNumber(p.value[1])}` } : undefined,
        markLine: hasTarget
          ? {
              silent: true,
              symbol: "none",
              lineStyle: { type: "dashed", color: MARK_LINE_COLOR, width: 1.5 },
              label: {
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                formatter: (p: any): string => `目標價 NT$${formatNumber(p.value)}`,
                color: "#92400e",
                backgroundColor: "#fff7e6",
                borderColor: MARK_LINE_COLOR,
                borderWidth: 1,
                borderRadius: 6,
                padding: [2, 8],
                fontSize: 12,
                position: "insideEndTop",
              },
              data: [{ yAxis: props.targetPrice }],
            }
          : undefined,
      },
    ],
  }
  return option
}

function initChart(): void {
  if (chart || !el.value || el.value.clientWidth === 0) return // E16：0 寬容器延後 init
  chart = echarts.init(el.value)
  chart.setOption(buildOption())
}

function render(): void {
  if (!chart) return
  chart.setOption(buildOption(), { notMerge: true })
  chart.resize()
}

onMounted(() => {
  initChart()
  observer = new ResizeObserver(() => {
    if (!chart && el.value && el.value.clientWidth > 0) initChart()
    else chart?.resize()
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
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div ref="el" class="price-trend-chart" role="img" aria-label="歷史價格趨勢圖" />
</template>

<style scoped>
.price-trend-chart {
  width: 100%;
  height: 360px;
}
</style>
