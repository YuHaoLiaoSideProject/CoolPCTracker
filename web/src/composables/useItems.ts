// web/src/composables/useItems.ts — 資料載入（開發規格 003 §2.4 / 004 §2.3）
// 職責：runtime 兩段式 fetch（AirTicketsPrice 模式，無 build 注入版本）：
//   1. fetch(BASE_URL + "api/index.json") → 取 latest_version（index 為唯一入口/目錄）
//   2. fetch(BASE_URL + "api/items/v{latest_version}.json") → 版本化快照（檔名自帶快取失效）
// 解析與 shape 驗證（parseItemsFile 相容 001 items.json 與 002 版本化快照兩種頂層形狀）、
// 錯誤分類、重試、過期判定。錯誤分類決定 ErrorState 顯示文案；任何失敗都不能影響側欄／
// 搜尋框渲染（錯誤只在列表區域呈現）。
// 003/004 共用 module-level 單例：列表頁與詳情頁共用同一份資料，避免重複請求（004 §2.3）。

import { ref, computed, type Ref } from "vue"
import type { ItemsFile, Item, PricePoint } from "@/types/item"

export type LoadError = "fetch" | "parse" | null
// 'fetch'：HTTP 失敗 / 網路中斷 → 「資料載入失敗」
// 'parse'：JSON 解析或 shape 驗證失敗 → 「資料格式錯誤」

export class ParseError extends TypeError {} // 供 error 分類判別

// 002 §1.7 合約（改造後）＋ AirTicketsPrice 模式：前端 runtime 發現，無 build 注入版本。
// index.json 是唯一入口（latest_version / latest_items），版本化快照 api/items/v{n}.json
// 檔名版本化 → 瀏覽器/Pages 快取對該檔必然失效，無需 query 快取穿透。
const INDEX_URL = `${import.meta.env.BASE_URL}api/index.json`

/** index.json shape 驗證：latest_version 為正整數（前端 runtime 發現的版本來源）。 */
export function parseIndex(raw: unknown): { latest_version: number } {
  if (!isRecord(raw)) throw new ParseError("index.json shape 不符：頂層應為 object")
  const v = raw.latest_version
  if (typeof v !== "number" || !Number.isInteger(v) || v < 1) {
    throw new ParseError("index.json shape 不符：latest_version 缺失或非正整數")
  }
  return { latest_version: v }
}

function createItemsState() {
  const items = ref<Item[]>([]) as Ref<Item[]>
  const meta = ref<ItemsFile["meta"] | null>(null)
  const loading = ref(true)
  const error = ref<LoadError>(null)

  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const indexRes = await fetch(INDEX_URL)
      if (!indexRes.ok) throw new Error(`HTTP ${indexRes.status}`)
      const indexRaw: unknown = await indexRes.json() // 壞 JSON → SyntaxError
      const { latest_version } = parseIndex(indexRaw) // shape 驗證失敗 → ParseError
      const itemsUrl = `${import.meta.env.BASE_URL}api/items/v${latest_version}.json`
      const itemsRes = await fetch(itemsUrl)
      if (!itemsRes.ok) throw new Error(`HTTP ${itemsRes.status}`)
      const raw: unknown = await itemsRes.json() // 壞 JSON → SyntaxError
      const parsed = parseItemsFile(raw) // shape 驗證失敗 → ParseError
      items.value = parsed.items
      meta.value = parsed.meta
    } catch (e) {
      error.value = e instanceof ParseError || e instanceof SyntaxError ? "parse" : "fetch"
      // items 保持上次成功資料（若有）或空陣列；絕不 throw 至元件層
    } finally {
      loading.value = false
    }
  }

  /** 過期判定：meta.crawled_at（UTC）距今 > 7 天（超過 7 天）→ true（顯示過期橫幅）。
   *  與 007 新鮮度規則共用；資料仍正常顯示。 */
  const isStale = computed(() => {
    if (!meta.value) return false
    const t = new Date(meta.value.crawled_at).getTime()
    if (Number.isNaN(t)) return false
    const days = Math.floor((Date.now() - t) / 86_400_000)
    return days > 7
  })

  load() // 首次建立即載入（單例建立一次，後續呼叫不重複 fetch）
  return { items, meta, loading, error, retry: load, isStale }
}

type ItemsState = ReturnType<typeof createItemsState>

// 004 §2.3：module-level 單例 —— 003 列表頁與 004 詳情頁共用同一份資料（避免重複請求）
let shared: ItemsState | null = null

export function useItems(): ItemsState {
  shared ??= createItemsState()
  return shared
}

/** 僅供測試重置單例（vitest 每個測試以獨立 stub fetch 驗證不同情境時呼叫） */
export function __resetItemsShared(): void {
  shared = null
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v)
}

/** 真資料 spec 形狀相容（crawler spec_parser 產出 {brand, model, extra:{...}}）：
 *  將 extra 內結構化欄位（vram_gb/chip/cores/…）平鋪至頂層，成為前端 ItemSpec
 *  （{brand, model, vram_gb, ...}）；null/undefined/空字串剔除（ItemSpec 契約不含 null），
 *  extra 巢狀鍵本身移除。無 extra 的舊形狀（平鋪欄位）原樣保留。 */
function normalizeSpec(spec: Record<string, unknown>): Item["spec"] {
  const out: Record<string, string | number | undefined> = {}
  const merge = (src: Record<string, unknown>): void => {
    for (const [k, v] of Object.entries(src)) {
      if (v === null || v === undefined || v === "") continue
      out[k] = v as string | number
    }
  }
  merge(spec)
  if (isRecord(spec.extra)) merge(spec.extra)
  delete out.extra
  return out
}

/** shape 驗證：接受兩種頂層形狀（前端契約相容）——
 *  ① 001 items.json：{ meta: { crawled_at, source }, items }
 *  ② 002 items.v{n}.json 快照：{ crawled_at, items }（頂層無 meta 巢狀）
 *  items 為陣列且每筆具 id/name/category；不符即拋 ParseError。
 *  正規化：原始 history 為 compact [d,p] 陣列（001 格式決策），此處 map 為 { d, p }（PricePoint）；
 *  缺 history/spec → 補預設值，避免下游 undefined 崩潰。 */
export function parseItemsFile(raw: unknown): ItemsFile {
  if (!isRecord(raw)) throw new ParseError("items.json shape 不符：頂層應為 object")
  const metaRaw = isRecord(raw.meta) ? raw.meta : {}
  const crawledAt =
    typeof metaRaw.crawled_at === "string"
      ? metaRaw.crawled_at
      : typeof raw.crawled_at === "string"
        ? raw.crawled_at
        : null
  if (!crawledAt) throw new ParseError("items.json shape 不符：meta.crawled_at 缺失")
  const rawItems = raw.items
  if (!Array.isArray(rawItems)) throw new ParseError("items.json shape 不符：items 應為陣列")

  const items: Item[] = rawItems.map((it: unknown, i: number): Item => {
    if (!isRecord(it)) throw new ParseError(`items[${i}] 非 object`)
    for (const key of ["id", "name", "category"] as const) {
      if (typeof it[key] !== "string") throw new ParseError(`items[${i}].${key} 缺失或非字串`)
    }
    const spec = isRecord(it.spec) ? normalizeSpec(it.spec) : {}
    const status = it.status === "gone" ? "gone" : "in_stock"
    const history = (Array.isArray(it.history) ? it.history : []).map((pt, j): PricePoint => {
      if (!Array.isArray(pt) || pt.length < 2 || typeof pt[0] !== "string" || typeof pt[1] !== "number") {
        throw new ParseError(`items[${i}].history[${j}] 格式不符（預期 compact [d, p]）`)
      }
      return { d: pt[0], p: pt[1] }
    })
    return {
      id: it.id as string,
      category: it.category as string,
      subcategory: typeof it.subcategory === "string" ? it.subcategory : undefined,
      name: it.name as string,
      spec,
      flags: isRecord(it.flags) ? (it.flags as Item["flags"]) : undefined,
      status,
      first_seen: typeof it.first_seen === "string" ? it.first_seen : "",
      last_seen: typeof it.last_seen === "string" ? it.last_seen : "",
      history,
    }
  })

  return {
    meta: {
      crawled_at: crawledAt,
      source: typeof metaRaw.source === "string" ? metaRaw.source : "",
    },
    items,
  }
}
