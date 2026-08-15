// web/src/composables/useCrawledAt.ts — crawled_at → 台北時間顯示＋過期判斷（開發規格 004 §2.6 / E11）
// 與 003 useItems.isStale／007 新鮮度規則共用同一過期規則：距今 > 7 天（超過 7 天）→ 過期。
import { computed, toValue, type ComputedRef, type MaybeRefOrGetter } from "vue"

const TAIPEI_TZ = "Asia/Taipei"
const DAY_MS = 86_400_000

/** UTC ISO → 台北時間字串（YYYY-MM-DD HH:mm，BDD E11：「2026-08-15 14:00」）；
 *  空值 → 「未知」；非法輸入 → 原字串回傳（不拋錯）。 */
export function formatCrawledAt(iso?: string | null): string {
  if (!iso) return "未知"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const parts = new Intl.DateTimeFormat("zh-TW", {
    timeZone: TAIPEI_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(d)
  const get = (type: Intl.DateTimeFormatPartTypes): string =>
    parts.find((p) => p.type === type)?.value ?? ""
  return `${get("year")}-${get("month")}-${get("day")} ${get("hour")}:${get("minute")}`
}

/** crawled_at 距今 > 7 天 → true（與 003 isStale 同一規則；資料仍正常顯示） */
export function isCrawledAtStale(iso?: string | null): boolean {
  if (!iso) return false
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return false
  const days = Math.floor((Date.now() - t) / DAY_MS)
  return days > 7
}

export interface CrawledAtState {
  /** 台北時間標籤（如 2026-08-15 14:00）；view 自行補「（台北時間）」後綴 */
  updatedLabel: ComputedRef<string>
  isStale: ComputedRef<boolean>
}

/** 輸入可為 getter（如 () => meta.value?.crawled_at）或 ref；回傳響應式標籤與過期旗標 */
export function useCrawledAt(crawledAt: MaybeRefOrGetter<string | null | undefined>): CrawledAtState {
  const updatedLabel = computed(() => formatCrawledAt(toValue(crawledAt)))
  const isStale = computed(() => isCrawledAtStale(toValue(crawledAt)))
  return { updatedLabel, isStale }
}
