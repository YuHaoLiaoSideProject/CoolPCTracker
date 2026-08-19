// web/src/types/dashboardFilter.ts — Dashboard 篩選狀態型別（022）

export type SortMode = "price_asc" | "price_desc" | "name_asc" | "name_desc" | "recently_updated"

export interface SortOption {
  value: SortMode
  label: string
}

export const SORT_OPTIONS: SortOption[] = [
  { value: "price_asc", label: "價格低→高" },
  { value: "price_desc", label: "價格高→低" },
  { value: "name_asc", label: "名稱 A→Z" },
  { value: "name_desc", label: "名稱 Z→A" },
  { value: "recently_updated", label: "最近更新" },
]
