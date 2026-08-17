// web/src/composables/usePriceHistory.ts — 詳情頁價格摘要（開發規格 004 §2.4）
// 漲跌計算委派 @/lib/priceChange（與 003 卡片共用同一事實來源）；此處僅補歷史最低價。
// 規則（含非連續日語意）：
//   previous = history 倒數第二筆（「上一筆有紀錄的日期」）、current = 最後一筆；diff = current - previous。
//   diff<0 → 降價（綠 ▼）、diff>0 → 漲價（紅 ▲）、diff===0 → 持平（灰 —）；
//   僅一筆 → previous=null，不計算漲跌（「首日追蹤，尚無漲跌比較」）。
//   歷史最低 = min(p)；lowDate 取最早達成日（history 依 d 升冪，第一個 p===min 的點）。

import { computed, type Ref } from "vue"
import type { PricePoint } from "@/types/item"
import { computePriceChange, type PriceTrend } from "@/lib/priceChange"

export type Trend = PriceTrend

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
    const change = computePriceChange(h)
    if (h.length === 0) {
      return { ...change, low: null, lowDate: null, empty: true, single: false }
    }
    const low = Math.min(...h.map((pt) => pt.p))
    const lowPoint = h.find((pt) => pt.p === low) // 升冪 → 第一個即最早達成日
    return {
      ...change,
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

// ---- 格式化 util（實作移至 @/lib/priceChange；此處 re-export 供既有 import 相容） ----

export { formatDiffAmount, formatDiffPercent, formatTrendLabel } from "@/lib/priceChange"
