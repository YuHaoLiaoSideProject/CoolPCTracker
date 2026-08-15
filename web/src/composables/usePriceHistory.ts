// web/src/composables/usePriceHistory.ts — 漲跌／歷史最低計算（開發規格 004 §2.4）
// 純函數計算抽離為可單元測試 util；Vitest 覆蓋 BDD E8（三態）、E9（最早達成日）、E5（單筆）。
// 規則：
//   previous = history[len-2]、current = history[len-1]；diff = current - previous。
//   diff<0 → 降價（綠 ▼）、diff>0 → 漲價（紅 ▲）、diff===0 → 持平（灰 —）；
//   僅一筆 → previous=null，不計算漲跌（「首日追蹤，尚無漲跌比較」）。
//   歷史最低 = min(p)；lowDate 取最早達成日（history 依 d 升冪，第一個 p===min 的點）。

import { computed, type Ref } from "vue"
import type { PricePoint } from "@/types/item"
import { formatNumber } from "@/utils/format"

export type Trend = "up" | "down" | "flat" | null

export interface PriceStats {
  current: number | null // history 最後一筆 p；空 history 為 null
  currentDate: string | null
  previous: number | null // 前一筆；僅一筆／空時為 null
  diff: number | null // current - previous
  diffPercent: number | null // diff / previous * 100
  trend: Trend
  low: number | null // 歷史最低價
  lowDate: string | null // 最早達成日
  empty: boolean // history 長度 0
  single: boolean // history 長度 1 → 首日追蹤
}

/** 以 history [d,p] 計算價格摘要（history 需依 d 升冪；PricePoint 由 useItems 自 compact [d,p] 正規化） */
export function usePriceHistory(history: Ref<PricePoint[]>) {
  const stats = computed<PriceStats>(() => {
    const h = history.value
    if (h.length === 0) {
      return {
        current: null,
        currentDate: null,
        previous: null,
        diff: null,
        diffPercent: null,
        trend: null,
        low: null,
        lowDate: null,
        empty: true,
        single: false,
      }
    }

    const current = h[h.length - 1].p
    const currentDate = h[h.length - 1].d
    const previous = h.length >= 2 ? h[h.length - 2].p : null

    let diff: number | null = null
    let diffPercent: number | null = null
    let trend: Trend = null
    if (previous != null) {
      diff = current - previous
      diffPercent = (diff / previous) * 100
      trend = diff > 0 ? "up" : diff < 0 ? "down" : "flat"
    }

    const low = Math.min(...h.map((pt) => pt.p))
    const lowPoint = h.find((pt) => pt.p === low) // 升冪 → 第一個即最早達成日

    return {
      current,
      currentDate,
      previous,
      diff,
      diffPercent,
      trend,
      low,
      lowDate: lowPoint?.d ?? null,
      empty: false,
      single: h.length === 1,
    }
  })

  /** 圖表資料序列（日期字串陣列、價格陣列） */
  const chartSeries = computed(() => ({
    dates: history.value.map((h) => h.d),
    prices: history.value.map((h) => h.p),
  }))

  return { stats, chartSeries }
}

// ---- 格式化 util（獨立 export，供 003 sparkline／卡片漲跌與 005 複用） ----

/** 漲跌金額標籤：diff<0 → 「降價 NT$510」；diff>0 → 「漲價 NT$100」（金額取絕對值、千分位） */
export function formatDiffAmount(diff: number): string {
  const verb = diff < 0 ? "降價" : "漲價"
  return `${verb} NT$${formatNumber(Math.abs(diff))}`
}

/** 漲跌百分比標籤：帶符號 1 位小數，「-4.9%」／「+5.3%」／「0.0%」 */
export function formatDiffPercent(diff: number, previous: number): string {
  const pct = (diff / previous) * 100
  const sign = pct > 0 ? "+" : ""
  return `${sign}${pct.toFixed(1)}%`
}

/** 完整漲跌標籤（view 直接使用）：降價 NT$510（-4.9%）／漲價 NT$100（+5.3%）／持平（BDD E8） */
export function formatTrendLabel(diff: number, previous: number): string {
  if (diff === 0) return "持平"
  return `${formatDiffAmount(diff)}（${formatDiffPercent(diff, previous)}）`
}
