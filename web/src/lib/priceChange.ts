// web/src/lib/priceChange.ts — 漲跌計算共用純函數（003 卡片 badge / 004 詳情頁摘要共用）
// 單一事實來源：usePriceDelta（卡片）與 usePriceHistory（詳情頁）皆委派至此，
// 不再各自實作「取最後兩點」邏輯（DRY）。
//
// 語意（crawler store.py 契約：history 依 d 升冪、每日一點累積含平價日；失敗分類商品不累積 → 仍可能有跨日缺口）：
//   - current = 最後一點（最新價）；previous = 倒數第二點 = 「上一筆有紀錄的日期」的價格。
//   - 「與前一日比較」實作上為「與上一筆有紀錄的日期比較」：history 無逐日紀錄，
//     非連續日（如 08-10 → 08-15）仍以最後兩點比較，不補中間日、不以日曆昨日猜測。
//   - 僅 1 筆 / 空 history → previous/diff/diffPercent/trend 全 null（上游優雅降級，不壞）。

import type { PricePoint } from "@/types/item"
import { formatNumber } from "@/utils/format"

export type PriceTrend = "up" | "down" | "flat" | null

export interface PriceChange {
  current: number | null // 最新價 = history 最後一點
  currentDate: string | null
  previous: number | null // 上一筆有紀錄的價格（非日曆昨日）
  previousDate: string | null
  diff: number | null // current - previous
  diffPercent: number | null // diff / previous * 100
  trend: PriceTrend
  hasPrevious: boolean // 是否有前一筆可比較（≥2 點）
}

/** history（升冪、PricePoint[]）→ 漲跌摘要；空/單點回傳 null 欄位（不 throw）。 */
export function computePriceChange(history: PricePoint[]): PriceChange {
  const n = history.length
  if (n === 0) {
    return {
      current: null,
      currentDate: null,
      previous: null,
      previousDate: null,
      diff: null,
      diffPercent: null,
      trend: null,
      hasPrevious: false,
    }
  }
  const current = history[n - 1].p
  const currentDate = history[n - 1].d
  if (n === 1) {
    return {
      current,
      currentDate,
      previous: null,
      previousDate: null,
      diff: null,
      diffPercent: null,
      trend: null,
      hasPrevious: false,
    }
  }
  const prev = history[n - 2]
  const diff = current - prev.p
  return {
    current,
    currentDate,
    previous: prev.p,
    previousDate: prev.d,
    diff,
    diffPercent: (diff / prev.p) * 100,
    trend: diff > 0 ? "up" : diff < 0 ? "down" : "flat",
    hasPrevious: true,
  }
}

// ---- 卡片 badge（003 BDD §「昨日漲跌」）----

/** badge 文字：漲/跌/持平；僅 1 筆（首日追蹤，有價無前）→「新」；空 history（無價）→「—」。 */
export function priceChangeBadgeText(c: PriceChange): string {
  if (c.current == null) return "—"
  if (c.diff == null) return "新"
  if (c.diff === 0) return "持平"
  const sign = c.diff > 0 ? "漲" : "跌"
  return `${sign} ${formatNumber(Math.abs(c.diff))}`
}

/** badge class：漲紅 price-up / 跌綠 price-down / 持平灰 price-flat / 新 price-new（中性）；空 history 無 class。 */
export function priceChangeBadgeClass(c: PriceChange): string {
  if (c.trend === "up") return "price-up"
  if (c.trend === "down") return "price-down"
  if (c.trend === "flat") return "price-flat"
  if (c.current != null) return "price-new"
  return ""
}

// ---- 詳情頁摘要（004 BDD E8：金額＋百分比）----

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

/** 完整漲跌標籤（詳情頁直接使用）：降價 NT$510（-4.9%）／漲價 NT$100（+5.3%）／持平（004 BDD E8） */
export function formatTrendLabel(diff: number, previous: number): string {
  if (diff === 0) return "持平"
  return `${formatDiffAmount(diff)}（${formatDiffPercent(diff, previous)}）`
}
