// web/src/utils/format.ts — 價格/日期格式化（NT$、台北時間）（開發規格 003 §2.1）

/** 價格格式化：28990 → "NT$ 28,990"（zh-TW 千分位 + NT$ 前綴） */
export function formatPrice(p: number): string {
  return `NT$ ${p.toLocaleString("zh-TW")}`
}

/** 數值千分位（漲跌金額用） */
export function formatNumber(n: number): string {
  return n.toLocaleString("zh-TW")
}

const TAIPEI_TZ = "Asia/Taipei"

/** UTC ISO → 台北時間顯示（如 2026/8/15 14:00）；解析失敗回傳原字串 */
export function formatDateTime(iso?: string): string {
  if (!iso) return "未知"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return new Intl.DateTimeFormat("zh-TW", {
    timeZone: TAIPEI_TZ,
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d)
}

/** UTC ISO → 台北時間日期（2026/8/15） */
export function formatDate(iso?: string): string {
  if (!iso) return "未知"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return new Intl.DateTimeFormat("zh-TW", {
    timeZone: TAIPEI_TZ,
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).format(d)
}
