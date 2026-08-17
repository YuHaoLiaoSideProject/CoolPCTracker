// web/src/composables/useItems.ts — 資料載入（契約 v2：分類分檔 + lazy 載入，2026-08-17）
// 職責（v2）：runtime fetch api/index.json（唯一入口/目錄，不再有 latest_file）
//   → 取得 categories[]（{id, name, file, count}）與 crawled_at。
//   → **lazy 載入**：建立即載入「目前選中分類」（第一個分類，依 categories 順序）；
//     loadCategory(id) 載入指定分類（已載入即快取命中、不重複 fetch）；
//     loadAll() 載入全部分類（全站搜尋／詳情 deep link 需要時呼叫）。
//   跨分類聚合：前端自建 itemId → categoryId 對照（itemToCategory map）；Item 本身無 category。
//   分類檔每日覆寫、URL 不帶日期 → 以 index.crawled_at 組 `?v=` 快取穿透
//   （fetch api/items/{file}?v={crawled_at}）。
// 解析與 shape 驗證（parseItemsFile 相容 v2 純陣列與舊 {items} 形狀）、錯誤分類、重試、
// 過期判定。錯誤分類決定 ErrorState 顯示文案；任何失敗都不 throw（元件層僅顯示錯誤區塊）。
// O4：完整歷史改由 api/trends/{id}.json 提供（詳情趨勢圖用），useTrend 依 id 載入並
// 正規化為 PricePoint[]（錯誤分類與列表共用 fetch/parse 語意）。
// 003/004 共用 module-level 單例：列表頁與詳情頁共用同一份資料，避免重複請求（004 §2.3）。

import { ref, computed, toValue, watch, isRef, type MaybeRefOrGetter, type Ref } from "vue"
import type { CategoryMeta, Item, ItemsFile, PricePoint, TrendFile } from "@/types/item"

export type LoadError = "fetch" | "parse" | null
// 'fetch'：HTTP 失敗 / 網路中斷 → 「資料載入失敗」
// 'parse'：JSON 解析或 shape 驗證失敗 → 「資料格式錯誤」

export class ParseError extends TypeError {} // 供 error 分類判別

// 契約 v2：index.json 是唯一入口（categories 目錄）；不再有 latest_file。
const INDEX_URL = `${import.meta.env.BASE_URL}api/index.json`

/** index.json（v2）shape 驗證：{crawled_at, source, categories:[{id,name,file,count}]}。 */
export interface ParsedIndex {
  categories: CategoryMeta[]
  crawledAt: string
  source: string
  total: number
}

export function parseIndex(raw: unknown): ParsedIndex {
  if (!isRecord(raw)) throw new ParseError("index.json shape 不符：頂層應為 object")
  const crawledAt = typeof raw.crawled_at === "string" && raw.crawled_at !== "" ? raw.crawled_at : null
  if (!crawledAt) throw new ParseError("index.json shape 不符：crawled_at 缺失或非字串")
  if (!Array.isArray(raw.categories)) throw new ParseError("index.json shape 不符：categories 應為陣列")
  const categories = raw.categories.map((c: unknown, i: number): CategoryMeta => {
    if (!isRecord(c)) throw new ParseError(`index.json shape 不符：categories[${i}] 非 object`)
    const id = c.id
    const file = c.file
    if (typeof id !== "string" || id === "") throw new ParseError(`index.json shape 不符：categories[${i}].id 缺失或非字串`)
    if (typeof file !== "string" || file === "") throw new ParseError(`index.json shape 不符：categories[${i}].file 缺失或非字串`)
    return {
      id,
      name: typeof c.name === "string" ? c.name : "",
      file,
      count: typeof c.count === "number" ? c.count : 0,
    }
  })
  return {
    categories,
    crawledAt,
    source: typeof raw.source === "string" ? raw.source : "",
    total: typeof raw.total === "number" ? raw.total : 0,
  }
}

function createItemsState() {
  // —— 分類目錄與索引 meta（index.json）——
  const categories = ref<CategoryMeta[]>([]) as Ref<CategoryMeta[]>
  const meta = ref<ItemsFile["meta"] | null>(null)

  // —— 已載入資料（「只增不減」的快取語意：lazy 載入後切換不回退）——
  const items = ref<Item[]>([]) as Ref<Item[]>
  const itemToCategory = ref<Map<string, string>>(new Map()) as Ref<Map<string, string>> // itemId → categoryId（前端自建對照）
  const loadedIds = ref<Set<string>>(new Set()) as Ref<Set<string>> // 已成功載入的分類 id（快取）
  const categoryLoading = ref<Record<string, boolean>>({}) as Ref<Record<string, boolean>> // 分類級載入旗標

  // —— 目前選中分類（null = 全部）——
  const activeCategoryId = ref<string | null>(null)
  const loading = ref(false) // 任一實體 fetch 進行中（index 或分類檔）
  const error = ref<LoadError>(null)

  const indexLoaded = ref(false) // index.json 是否成功載入（retry 分流用）
  let failure: LoadError = null // loadAll 聚合錯誤暫存（parallel 下最後寫入）
  let activeLoads = 0 // fetch 計數器 → loading 布林
  const inFlight = new Map<string, Promise<void>>() // 分類級 in-flight 去重（同 id 併發只 fetch 一次）

  function beginLoad() {
    activeLoads += 1
    loading.value = true
  }
  function endLoad() {
    activeLoads -= 1
    if (activeLoads <= 0) {
      activeLoads = 0
      loading.value = false
    }
  }
  function setCategoryLoading(id: string, v: boolean) {
    const next = { ...categoryLoading.value }
    if (v) next[id] = true
    else delete next[id]
    categoryLoading.value = next
  }
  function classify(e: unknown): LoadError {
    return e instanceof ParseError || e instanceof SyntaxError ? "parse" : "fetch"
  }
  function categoryFile(id: string): string | null {
    return categories.value.find(c => c.id === id)?.file ?? null
  }
  function itemFileUrl(file: string): string {
    const v = meta.value?.crawled_at ? `?v=${encodeURIComponent(meta.value.crawled_at)}` : ""
    return `${import.meta.env.BASE_URL}${file}${v}`
  }

  /** 抓取單一分類檔（不含 active 指派 — loadAll 併發用）。已載入→立即返回；in-flight→等待同一 Promise。 */
  async function fetchCategory(id: string): Promise<void> {
    const file = categoryFile(id)
    if (!file) return
    const pending = inFlight.get(id)
    if (pending) return pending
    if (loadedIds.value.has(id)) return
    const p = (async () => {
      beginLoad()
      setCategoryLoading(id, true)
      try {
        const res = await fetch(itemFileUrl(file))
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const raw: unknown = await res.json() // 壞 JSON → SyntaxError
        const parsed = parseItemsFile(raw, { crawledAt: meta.value?.crawled_at ?? "" }) // shape 驗證失敗 → ParseError
        // 追加（快取語意：只增不減）；同 id 商品重複出現（跨分類理論上不會）以 map 去重
        const map = new Map(itemToCategory.value)
        const fresh = parsed.items.filter(it => !map.has(it.id))
        for (const it of fresh) map.set(it.id, id)
        if (fresh.length) {
          items.value = [...items.value, ...fresh]
          itemToCategory.value = map
        }
        loadedIds.value = new Set(loadedIds.value).add(id)
        error.value = null // 此分類成功 → 清錯誤（loadAll 聚合在收尾統一判定）
      } catch (e) {
        error.value = classify(e) // 失敗：不加入 loadedIds（retry 可重抓）
        failure = error.value
      } finally {
        setCategoryLoading(id, false)
        endLoad()
        inFlight.delete(id)
      }
    })()
    inFlight.set(id, p)
    return p
  }

  /** 載入指定分類並設為目前選中（快取已載入 → 立即切換、不重複 fetch）。 */
  async function loadCategory(id: string): Promise<void> {
    if (!categoryFile(id)) return // 分類目錄未就緒／未知 id → no-op（等 categories watch 重試）
    activeCategoryId.value = id
    if (loadedIds.value.has(id)) {
      error.value = null // 切換到已成功載入的分類 → 視為復原（清掉背景失敗的錯誤旗標）
      return
    }
    await fetchCategory(id)
  }

  /** 載入全部分類並切至「全部」視圖（全站搜尋／詳情 deep link）。已載入分類不重複 fetch。 */
  async function loadAll(): Promise<void> {
    activeCategoryId.value = null
    const ids = categories.value.filter(c => !loadedIds.value.has(c.id) && !inFlight.has(c.id)).map(c => c.id)
    if (!ids.length) return
    failure = null
    await Promise.all(ids.map(id => fetchCategory(id)))
    // 聚合錯誤判定：任一失敗 → 保留錯誤（其餘成功分類照常顯示）；全成功 → 清空
    error.value = failure ?? null
  }

  /** 抓取 index.json → 目錄/meta 就緒 → 自動載入第一個分類（預設選中，依 categories 順序）。 */
  async function fetchIndex(): Promise<void> {
    const res = await fetch(INDEX_URL)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const raw: unknown = await res.json() // 壞 JSON → SyntaxError
    const parsed = parseIndex(raw) // shape 驗證失敗 → ParseError
    categories.value = parsed.categories
    meta.value = { crawled_at: parsed.crawledAt, source: parsed.source }
    indexLoaded.value = true
    error.value = null
  }

  async function bootstrap(): Promise<void> {
    beginLoad()
    failure = null
    try {
      await fetchIndex()
      const first = activeCategoryId.value ?? categories.value[0]?.id ?? null
      if (first) {
        activeCategoryId.value = first
        await fetchCategory(first) // 失敗已分類於內部，不 throw
      }
      error.value = failure ?? null
    } catch (e) {
      error.value = classify(e) // index 失敗 → fetch/parse
    } finally {
      endLoad()
    }
  }

  /** 重試目前意圖：index 未就緒 → 重新 bootstrap；否則重載目前選中（分類或全部）。 */
  async function retry(): Promise<void> {
    if (!indexLoaded.value) {
      await bootstrap()
      return
    }
    error.value = null
    if (activeCategoryId.value) await loadCategory(activeCategoryId.value)
    else await loadAll()
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

  /** 分類級載入中判定（側欄/列表切換時顯示 loading 用） */
  function isLoadingCategory(id: string): boolean {
    return categoryLoading.value[id] === true || inFlight.has(id)
  }

  bootstrap() // 單例建立即載入（index + 預設第一分類，lazy）
  return {
    items,
    meta,
    loading,
    error,
    retry,
    isStale,
    categories,
    activeCategoryId,
    itemToCategory,
    loadedIds,
    loadCategory,
    loadAll,
    isLoadingCategory,
  }
}

export type ItemsState = ReturnType<typeof createItemsState>

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

/** 原始 compact history（[d, p] 陣列）→ PricePoint[]；格式不符拋 ParseError。
 *  共用於分類檔（parseItemsFile，每筆 ≤2 點）與 trends 檔（parseTrendFile，全歷史）。 */
function parseCompactHistory(raw: unknown, ctx: string): PricePoint[] {
  if (!Array.isArray(raw)) throw new ParseError(`${ctx} 應為陣列`)
  return raw.map((pt, j): PricePoint => {
    if (!Array.isArray(pt) || pt.length < 2 || typeof pt[0] !== "string" || typeof pt[1] !== "number") {
      throw new ParseError(`${ctx}[${j}] 格式不符（預期 compact [d, p]）`)
    }
    return { d: pt[0], p: pt[1] }
  })
}

export interface ParseItemsFileOptions {
  /** 契約 v2：分類檔為純陣列（無 meta），crawled_at 由呼叫端注入（index.crawled_at）。 */
  crawledAt?: string | null
}

/** shape 驗證（契約 v2）：接受三種輸入——
 *  ① v2 分類檔：**頂層 array**（單一分類 items；每筆**無 category 欄位**；crawledAt 由選項注入）
 *  ② 舊 001 items.json：{ meta: { crawled_at, source }, items }
 *  ③ 舊 002 日期制快照：{ crawled_at, items }（頂層無 meta 巢狀）
 *  items 每筆具 id/name；**不再要求 category**（v2 移除；舊資料的 category 欄位被忽略）。
 *  正規化：原始 history 為 compact [d,p] 陣列（001 格式決策），此處 map 為 { d, p }（PricePoint）；
 *  缺 history/spec → 補預設值，避免下游 undefined 崩潰。
 *  O4 相容：history 為「最近 ≤2 點」（甚至 0/1 點，如新商品）照常 parse，無長度下限。 */
export function parseItemsFile(raw: unknown, opts: ParseItemsFileOptions = {}): ItemsFile {
  let rawItems: unknown = null
  let crawledAt = opts.crawledAt ?? null
  let source = ""

  if (Array.isArray(raw)) {
    // ① v2 純陣列檔
    rawItems = raw
  } else if (isRecord(raw)) {
    // ②③ 舊形狀（回溯相容）
    const metaRaw = isRecord(raw.meta) ? raw.meta : {}
    if (crawledAt == null) {
      crawledAt =
        typeof metaRaw.crawled_at === "string" && metaRaw.crawled_at !== ""
          ? metaRaw.crawled_at
          : typeof raw.crawled_at === "string" && raw.crawled_at !== ""
            ? raw.crawled_at
            : null
    }
    source = typeof metaRaw.source === "string" ? metaRaw.source : typeof raw.source === "string" ? raw.source : ""
    rawItems = raw.items
    if (!Array.isArray(rawItems)) throw new ParseError("items.json shape 不符：items 應為陣列")
  } else {
    throw new ParseError("items.json shape 不符：頂層應為 object 或陣列")
  }

  // v2 純陣列檔無 meta：呼叫端未注入 crawledAt 時以空字串相容（不拋）；舊形狀則維持原契約（必填）
  if (crawledAt == null) {
    if (Array.isArray(raw)) crawledAt = ""
    else throw new ParseError("items.json shape 不符：meta.crawled_at 缺失")
  }

  const items: Item[] = (rawItems as unknown[]).map((it: unknown, i: number): Item => {
    if (!isRecord(it)) throw new ParseError(`items[${i}] 非 object`)
    for (const key of ["id", "name"] as const) {
      if (typeof it[key] !== "string" || it[key] === "") throw new ParseError(`items[${i}].${key} 缺失或非字串`)
    }
    const spec = isRecord(it.spec) ? normalizeSpec(it.spec) : {}
    const status = it.status === "gone" ? "gone" : "in_stock"
    const history = it.history === undefined ? [] : parseCompactHistory(it.history, `items[${i}].history`)
    return {
      id: it.id as string,
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

  return { meta: { crawled_at: crawledAt, source }, items }
}

// ---- O4：trends 檔（api/trends/{id}.json，完整歷史） ----

/** shape 驗證：{ id: 非空字串, history: compact [d, p] 陣列（依 d 升冪、可為空）}。
 *  正規化：history 由 compact [d,p] map 為 { d, p }（PricePoint）；不符即拋 ParseError。 */
export function parseTrendFile(raw: unknown): TrendFile {
  if (!isRecord(raw)) throw new ParseError("trends.json shape 不符：頂層應為 object")
  if (typeof raw.id !== "string" || raw.id.length === 0) {
    throw new ParseError("trends.json shape 不符：id 缺失或非字串")
  }
  const history = parseCompactHistory(raw.history, "trends.json.history")
  return { id: raw.id, history }
}

export interface TrendState {
  history: Ref<PricePoint[]> // 完整歷史（升冪）；載入中/失敗時為上次成功資料或 []
  loading: Ref<boolean>
  error: Ref<LoadError> // 'fetch'：HTTP 失敗；'parse'：JSON/shape 驗證失敗
  retry: () => Promise<void>
}

/** 依商品 id 載入完整歷史（O4：api/trends/{id}.json，詳情趨勢圖用）。
 *  id 可為 ref/getter（路由參數變化自動重新載入）；undefined/空 → 不 fetch、回空歷史。
 *  錯誤分類沿用 useItems 的 fetch/parse 語意，任何失敗皆不 throw（元件層僅顯示錯誤區塊）。 */
export function useTrend(id: MaybeRefOrGetter<string | undefined>): TrendState {
  const history = ref<PricePoint[]>([]) as Ref<PricePoint[]>
  const loading = ref(true)
  const error = ref<LoadError>(null)

  async function load(): Promise<void> {
    const trendId = toValue(id)
    if (!trendId) {
      // 無 id（如路由尚未就緒）：視為空資料而非錯誤
      history.value = []
      error.value = null
      loading.value = false
      return
    }
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`${import.meta.env.BASE_URL}api/trends/${trendId}.json`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const raw: unknown = await res.json() // 壞 JSON → SyntaxError
      const parsed = parseTrendFile(raw) // shape 驗證失敗 → ParseError
      history.value = parsed.history
    } catch (e) {
      error.value = e instanceof ParseError || e instanceof SyntaxError ? "parse" : "fetch"
      // history 保持上次成功資料（若有）或空陣列；絕不 throw 至元件層
    } finally {
      loading.value = false
    }
  }

  // 僅 watch 可響應來源（ref／getter）；靜態字串 id 直接載入一次（watch 對原始值無意義且會警告）
  if (typeof id === "function" || isRef(id)) {
    watch(id, load, { immediate: true })
  } else {
    void load()
  }
  return { history, loading, error, retry: load }
}