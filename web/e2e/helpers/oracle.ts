// web/e2e/helpers/oracle.ts — 測試 oracle（以真實資料檔動態計算，避免寫死會漂移的筆數）
// 讀取 data/items.v2.json（與 dev server 服務的 web/public/data/items.v2.json 相同內容），
// 鏡像前端 useItems.parseItemsFile 的 normalizeSpec 與 search.ts / specFilter.ts 的比對邏輯，
// 產出「前端應顯示的結果集合」，供 E2E 斷言對照。
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"

export interface RawSpec {
  [key: string]: unknown
}

export interface RawItem {
  id: string
  name: string
  category: string
  spec?: RawSpec
  [key: string]: unknown
}

/** 鏡像 useItems.normalizeSpec：將 extra 平鋪至頂層、剔除 null/undefined/空字串 */
export function flatSpec(spec: RawSpec | null | undefined): Record<string, string | number | undefined> {
  const out: Record<string, string | number | undefined> = {}
  const merge = (src: Record<string, unknown>): void => {
    for (const [k, v] of Object.entries(src)) {
      if (v === null || v === undefined || v === "") continue
      out[k] = v as string | number
    }
  }
  if (spec) {
    merge(spec)
    const extra = spec.extra
    if (extra && typeof extra === "object" && !Array.isArray(extra)) {
      merge(extra as Record<string, unknown>)
    }
  }
  delete out.extra
  return out
}

/** 載入真資料 items（與前端 dev server 服務的 items.v2.json 一致） */
export function loadItems(): RawItem[] {
  const url = new URL("../../../data/items.v2.json", import.meta.url)
  const raw = JSON.parse(readFileSync(fileURLToPath(url), "utf-8"))
  if (!Array.isArray(raw.items)) throw new Error("oracle: data/items.v2.json 缺少 items 陣列")
  return raw.items as RawItem[]
}

/** 鏡像 search.ts matchesKeyword（name + spec 欄位值字面比對，不區分大小寫） */
export function matchesKeyword(it: RawItem, q: string): boolean {
  const needle = q.toLowerCase()
  if (it.name.toLowerCase().includes(needle)) return true
  const specText = Object.values(flatSpec(it.spec))
    .map(v => String(v ?? ""))
    .join(" ")
    .toLowerCase()
  return specText.includes(needle)
}

/** 鏡像 specFilter.matchesCondition（缺欄位/非 number → false 靜默排除；v >= threshold） */
export function matchesCondition(it: RawItem, field: string, threshold: number): boolean {
  const v = flatSpec(it.spec)[field]
  return typeof v === "number" && v >= threshold
}

/** 套用「規格條件 AND」於指定集合 */
export function applyConditions(items: RawItem[], conds: { field: string; threshold: number }[]): RawItem[] {
  return items.filter(it => conds.every(c => matchesCondition(it, c.field, c.threshold)))
}

/** 搜尋 + 規格條件同時作用（鏡像 useFilters 過濾管線） */
export function filterByKeywordAndConditions(
  items: RawItem[],
  keyword: string,
  conds: { field: string; threshold: number }[],
): RawItem[] {
  const q = keyword.trim().toLowerCase()
  return items.filter(it => {
    if (q && !matchesKeyword(it, q)) return false
    return conds.every(c => matchesCondition(it, c.field, c.threshold))
  })
}

/** 排序後的名稱陣列，供集合相等斷言（DOM 顯示順序與資料順序可能不同） */
export function sortedNames(items: RawItem[]): string[] {
  return items.map(it => it.name).sort()
}
