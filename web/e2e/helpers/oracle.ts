// web/e2e/helpers/oracle.ts — 測試 oracle（以真實資料檔動態計算，避免寫死會漂移的筆數）
// 契約 v2：讀 ../api/index.json 的 categories[]（{id, name, file, count}）＋ crawled_at，
// 依分類目錄逐一載入 api/items/{file}（純陣列、每筆無 category 欄位），以 crawled_at 組
// `?v=` 快取穿透 URL（與前端 useItems 的 itemFileUrl 語意一致），動態聚合出「前端應顯示的
// 結果集合」供 E2E 斷言對照。v2 不再有 latest_file / 單一日期制快照。
// 分類為外部狀態：載入時將分類名 stamp 回每筆 item（category 欄位），維持舊 oracle 語意
// （記憶體/SSD/HDD 等跨分類排除斷言可直接使用 ITEMS.category）。
// 鏡像前端 useItems.parseItemsFile 的 normalizeSpec 與 search.ts / specFilter.ts 的比對邏輯。
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

export interface CategoryMeta {
  id: string
  name: string
  file: string // api/items/{file} 檔名（可為 "api/items/4.json" 全路徑或 "4.json" 單檔名）
  count: number
}

export interface ParsedIndex {
  categories: CategoryMeta[]
  crawledAt: string
  total: number
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

/** 讀 ../api/index.json（v2 契約：categories[] 目錄 + crawled_at；無 latest_file） */
function resolveIndex(): ParsedIndex {
  const indexUrl = new URL("../../../api/index.json", import.meta.url)
  const raw = JSON.parse(readFileSync(fileURLToPath(indexUrl), "utf-8")) as {
    categories?: unknown
    crawled_at?: unknown
    total?: unknown
  }
  if (!Array.isArray(raw.categories) || raw.categories.length === 0) {
    throw new Error("oracle: api/index.json 缺少 categories[]，無法解析分類目錄")
  }
  if (typeof raw.crawled_at !== "string" || raw.crawled_at.length === 0) {
    throw new Error("oracle: api/index.json 缺少 crawled_at，無法組 ?v= 快取穿透參數")
  }
  const categories = raw.categories.map((c: unknown, i: number): CategoryMeta => {
    const rec = c as { id?: unknown; name?: unknown; file?: unknown; count?: unknown }
    if (typeof rec.id !== "string" || typeof rec.name !== "string" || typeof rec.file !== "string") {
      throw new Error(`oracle: api/index.json categories[${i}] 缺少 id/name/file`)
    }
    return { id: rec.id, name: rec.name, file: rec.file, count: typeof rec.count === "number" ? rec.count : 0 }
  })
  return { categories, crawledAt: raw.crawled_at, total: typeof raw.total === "number" ? raw.total : 0 }
}

/** 分類檔名正規化：categories[].file 可能是全路徑（"api/items/4.json"）或單檔名（"4.json"）→ 回單檔名 */
function normalizeFileBasename(file: string): string {
  const prefix = "api/items/"
  return file.startsWith(prefix) ? file.slice(prefix.length) : file
}

/** 分類檔 URL（鏡像前端 itemFileUrl：api/items/{basename}?v={crawled_at} 快取穿透） */
export function categoryFileUrl(file: string, crawledAt: string): string {
  const v = encodeURIComponent(crawledAt)
  return `api/items/${normalizeFileBasename(file)}?v=${v}`
}

/** 分類檔在本機 repo 的實際路徑（oracle 直接讀 api/ 原始檔，不走 HTTP） */
function categoryRepoPath(file: string): string {
  const url = new URL(`../../../api/items/${normalizeFileBasename(file)}`, import.meta.url)
  return fileURLToPath(url)
}

const INDEX = resolveIndex()

/** 載入真資料 items（v2：依 categories[] 逐一讀取分類檔並聚合；每筆 stamp 分類名）。
 *  與前端 useItems 的 loadAll() 語意一致（全部分類併集，跨分類搜尋/篩選基準）。 */
export function loadItems(): RawItem[] {
  const all: RawItem[] = []
  for (const cat of INDEX.categories) {
    const raw = JSON.parse(readFileSync(categoryRepoPath(cat.file), "utf-8"))
    if (!Array.isArray(raw)) throw new Error(`oracle: ${cat.file} 應為純陣列（v2 分類檔）`)
    for (const it of raw) {
      const item = it as RawItem
      all.push({ ...item, category: item.category ?? cat.name })
    }
  }
  return all
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

export { INDEX }