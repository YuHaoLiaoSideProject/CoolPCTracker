// web/src/lib/priceTrend.ts — 價格走勢圖「組態/資料轉換」純函數（004）
// 抽離為純函數以便單元測試；PriceTrendChart.vue 直接消費。
// 關鍵決策（spike 報告 §2）：
//   - time 直接用 PricePoint.d 的 "yyyy-mm-dd" 字串（lwc Time = string），
//     勿用 new Date(d).getTime()（毫秒）——UTCTimestamp 單位是「秒」。
//   - 升冪、單日單點由契約保證，series.setData 傳 { time, value }[]。
import { ColorType, CrosshairMode, LineStyle } from "@/lib/lightweight-charts"
import type {
  CreatePriceLineOptions,
  DeepPartial,
  LineData,
  SeriesMarker,
  Time,
  TimeChartOptions,
} from "@/lib/lightweight-charts"
import type { PricePoint } from "@/types/item"
import { formatNumber } from "@/utils/format"

export const BRAND_COLOR = "#1f6feb" // 折線品牌色（tokens --brand）
export const TARGET_COLOR = "#f59e0b" // 目標價琥珀色（tokens --warning 對應）

const TEXT_COLOR = "#1f2937" // tokens --text
const GRID_COLOR = "#e5e7eb" // tokens --border
const CROSSHAIR_COLOR = "#6b7280" // tokens --text-dim

const pad2 = (n: number): string => String(n).padStart(2, "0")

/** PricePoint[] → lwc LineData[]（{ time, value }[]；time 為 "yyyy-mm-dd" 字串） */
export function buildSeriesData(history: PricePoint[]): LineData<Time>[] {
  return history.map((h) => ({ time: h.d, value: h.p }))
}

/** 資料點符號：單筆或 ≤24 點顯示 circle marker；單筆另附價格文字（lwc 無 showSymbol） */
export function buildMarkers(history: PricePoint[]): SeriesMarker<Time>[] {
  const single = history.length === 1
  if (!single && history.length > 24) return []
  return history.map(
    (h): SeriesMarker<Time> => ({
      time: h.d,
      position: "inBar",
      shape: "circle",
      color: BRAND_COLOR,
      ...(single ? { text: `NT$${formatNumber(h.p)}` } : {}),
    }),
  )
}

/** 目標價水平線：價格軸 title「目標價」（無圖內 badge，spike §2 最低成本替代） */
export function buildPriceLineOptions(price: number): CreatePriceLineOptions {
  return {
    price,
    color: TARGET_COLOR,
    lineStyle: LineStyle.Dashed,
    lineWidth: 2,
    title: "目標價",
    axisLabelVisible: true,
  }
}

/** chart 建立選項：明暗色沿用硬編碼 token（Canvas 不吃 CSS var，無動態主題） */
export function buildChartOptions(size: { width: number; height: number }): DeepPartial<TimeChartOptions> {
  return {
    width: size.width,
    height: size.height,
    layout: {
      background: { type: ColorType.Solid, color: "transparent" },
      textColor: TEXT_COLOR,
      fontSize: 12,
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: GRID_COLOR },
      horzLines: { color: GRID_COLOR },
    },
    crosshair: {
      mode: CrosshairMode.Magnet,
      vertLine: { color: CROSSHAIR_COLOR, labelBackgroundColor: BRAND_COLOR },
      horzLine: { color: CROSSHAIR_COLOR, labelBackgroundColor: BRAND_COLOR },
    },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false, rightOffset: 2 },
    localization: {
      locale: "zh-TW",
      dateFormat: "MM-dd",
      priceFormatter: (p: number) => `NT$${formatNumber(p)}`,
    },
  }
}

/** lwc Time（string/BusinessDay/UTCTimestamp）→ 工具提示日期 "yyyy-mm-dd" */
export function formatChartDate(time: Time): string {
  if (typeof time === "string") return time
  if (typeof time === "number") {
    const d = new Date(time * 1000) // UTCTimestamp 為秒
    return `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())}`
  }
  return `${time.year}-${pad2(time.month)}-${pad2(time.day)}`
}

/** 自訂 DOM tooltip 定位：偏移十字線 + 邊界 clamp（保持於容器內） */
export function computeTooltipPosition(
  point: { x: number; y: number },
  container: { width: number; height: number },
  tooltip: { width: number; height: number },
  gap = 12,
): { left: number; top: number } {
  let left = point.x + gap
  let top = point.y - tooltip.height - gap
  if (left + tooltip.width > container.width) left = point.x - tooltip.width - gap
  if (top < 0) top = point.y + gap
  left = Math.min(Math.max(gap, left), Math.max(gap, container.width - tooltip.width - gap))
  top = Math.min(Math.max(gap, top), Math.max(gap, container.height - tooltip.height - gap))
  return { left, top }
}
