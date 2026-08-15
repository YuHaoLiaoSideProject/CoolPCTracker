// web/src/data/categories.ts — 9 大分類固定常數（開發規格 003 §2.3）
// 與爬蟲 crawler/categories.py 同步（單一事實來源）；側欄只渲染此表 →
// 天然滿足 BDD「側欄不顯示追蹤範圍外的分類」。

export type CategoryKey =
  | "CPU" | "MB" | "RAM" | "GPU" | "SSD"
  | "HDD" | "DESKTOP" | "BUNDLE" | "CARD"

export interface CategoryDef {
  key: CategoryKey // URL 參數值，如 ?category=GPU
  label: string // 顯示名 + items.json 的 category 欄位值
  gIndex: number // 爬蟲手機版頁 G 索引（僅供對照，前端不使用）
}

export const CATEGORIES: CategoryDef[] = [
  { key: "CPU", label: "CPU", gIndex: 4 },
  { key: "MB", label: "主機板", gIndex: 5 },
  { key: "RAM", label: "記憶體", gIndex: 6 },
  { key: "GPU", label: "顯示卡", gIndex: 12 },
  { key: "SSD", label: "SSD", gIndex: 7 },
  { key: "HDD", label: "HDD", gIndex: 8 },
  { key: "DESKTOP", label: "套裝/準系統", gIndex: 1 },
  { key: "BUNDLE", label: "劈發價組合區", gIndex: 3 },
  { key: "CARD", label: "記憶卡", gIndex: 9 },
]

export const CATEGORY_KEYS: readonly string[] = CATEGORIES.map(c => c.key)

export function isCategoryKey(v: unknown): v is CategoryKey {
  return typeof v === "string" && (CATEGORY_KEYS as readonly string[]).includes(v)
}

export function labelOf(key: CategoryKey): string {
  const c = CATEGORIES.find(c => c.key === key)
  return c ? c.label : key
}
