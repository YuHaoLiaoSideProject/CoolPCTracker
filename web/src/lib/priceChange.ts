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
  lastChangedDate: string | null // 上次價格不同於前一次的日期（往前找第一個 diff≠0）
  daysSinceChange: number | null // 距今幾天（null = 找不到或無價格）
}

/** history（升冪、PricePoint[]）→ 漲跌摘要；空/單點回傳 null 欄位（不 throw）。 */
/** 從 history 尾端往前找，回傳第一個 price[n] ≠ price[n-1] 的「前一天」日期；
 * 即舊價格最後存在的日子（使用者預期：上次變動 9/9，非 9/10）。
 * 找不到回傳 null。 */
export function findLastChangeDate(history: PricePoint[]): string | null {
  for (let i = history.length - 1; i >= 1; i--) {
    if (history[i].p !== history[i - 1].p) return history[i - 1].d
  }
  // 全部相同（或僅 1 筆）→ 以第一筆日期為「起始日」
  return history.length > 0 ? history[0].d : null
}

/** 計算距今天數（以 UTC 日期字串比較，不涉時區）。 */
export function daysBetween(dateA: string, dateB: string): number {
  const a = new Date(dateA + "T00:00:00Z")
  const b = new Date(dateB + "T00:00:00Z")
  return Math.round((b.getTime() - a.getTime()) / 86_400_000)
}

export interface ComputePriceChangeOptions {
  /** O4：從完整歷史計算的變動前價格（卡片用，覆蓋 history 最後兩點計算） */
  previousPrice?: number | null
  /** O4：從完整歷史計算的上次變動日期（卡片用） */
  lastChangedDate?: string | null
}

export function computePriceChange(
  history: PricePoint[],
  options?: ComputePriceChangeOptions | string | null,
): PriceChange {
  // 相容舊呼叫：第二參數為 string 時視為 overrideLastChangedDate
  const opts: ComputePriceChangeOptions =
    typeof options === "string"
      ? { lastChangedDate: options }
      : options ?? {}

  const n = history.length
  // O4 修正：優先使用外部提供的 lastChangedDate；未提供時退回 findLastChangeDate
  const lastChangedDate =
    opts.lastChangedDate != null ? opts.lastChangedDate : findLastChangeDate(history)
  const today = new Date().toISOString().slice(0, 10)
  const daysSinceChange = lastChangedDate != null ? daysBetween(lastChangedDate, today) : null

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
      lastChangedDate: null,
      daysSinceChange: null,
    }
  }
  const current = history[n - 1].p
  const currentDate = history[n - 1].d

  // O4：有 previousPrice 時直接使用（從完整歷史計算）；否則退回 history 最後兩點
  const useOverride = opts.previousPrice != null
  const prev = useOverride ? opts.previousPrice! : n >= 2 ? history[n - 2].p : null
  const prevDate = useOverride ? lastChangedDate : n >= 2 ? history[n - 2].d : null

  if (prev == null) {
    return {
      current,
      currentDate,
      previous: null,
      previousDate: null,
      diff: null,
      diffPercent: null,
      trend: null,
      hasPrevious: false,
      lastChangedDate,
      daysSinceChange,
    }
  }

  const diff = current - prev
  return {
    current,
    currentDate,
    previous: prev,
    previousDate: prevDate,
    diff,
    diffPercent: (diff / prev) * 100,
    trend: diff > 0 ? "up" : diff < 0 ? "down" : "flat",
    hasPrevious: true,
    lastChangedDate,
    daysSinceChange,
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

// ---- 卡片價格年齡 badge（上次變動距今）----

/** 價格年齡文字：「今天」/「1天前」/「N天前」/「M/D」（>7天） */
export function priceAgeText(c: PriceChange): string {
  if (c.daysSinceChange == null) return ""
  if (c.daysSinceChange <= 0) return "今天"
  if (c.daysSinceChange === 1) return "昨天"
  if (c.daysSinceChange <= 7) return `${c.daysSinceChange}天前`
  // >7 天：顯示日期 M/D
  if (c.lastChangedDate) {
    const [, m, d] = c.lastChangedDate.split("-")
    return `${parseInt(m)}/${parseInt(d)}`
  }
  return `${c.daysSinceChange}天前`
}

/** 價格年齡 class：今天=藍色（fresh）、>3天=淡色（stale） */
export function priceAgeClass(c: PriceChange): string {
  if (c.daysSinceChange == null) return ""
  if (c.daysSinceChange <= 0) return "is-fresh"
  if (c.daysSinceChange > 3) return "is-stale"
  return ""
}

/** 價格年齡 tooltip 完整日期（2026 年 8 月 22 日） */
export function priceAgeTooltip(c: PriceChange): string {
  if (!c.lastChangedDate) return ""
  const [y, m, d] = c.lastChangedDate.split("-")
  return `${y} 年 ${parseInt(m)} 月 ${parseInt(d)} 日`
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
