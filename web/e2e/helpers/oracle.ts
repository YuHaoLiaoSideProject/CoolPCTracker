// web/e2e/helpers/oracle.ts — 測試 oracle（以真實資料檔動態計算，避免寫死會漂移的筆數）
// 讀 ../api/index.json 的 latest_file → 動態解析前端實際載入的日期制快照檔
// （與前端 useItems runtime 兩段式 fetch 一致），動態解析當前版本，避免資料版本 bump 後
// oracle 仍讀舊快照。
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

/** 讀 ../api/index.json 的 latest_file，動態解析前端實際載入的日期制資料檔 */
function resolveLatestFile(): string {
  const indexUrl = new URL("../../../api/index.json", import.meta.url)
  const index = JSON.parse(readFileSync(fileURLToPath(indexUrl), "utf-8")) as { latest_file?: unknown }
  if (typeof index.latest_file !== "string" || index.latest_file.length === 0) {
    throw new Error("oracle: api/index.json 缺少 latest_file，無法解析資料檔名")
  }
  return index.latest_file
}

/** 載入真資料 items（與前端 useItems 依 latest_file fetch 的日期制快照一致） */
export function loadItems(): RawItem[] {
  const file = resolveLatestFile()
  const url = new URL(`../../../${file}`, import.meta.url)
  const raw = JSON.parse(readFileSync(fileURLToPath(url), "utf-8"))
  if (!Array.isArray(raw.items)) throw new Error(`oracle: ${file} 缺少 items 陣列`)
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
