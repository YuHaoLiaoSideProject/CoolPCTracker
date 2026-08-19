// web/src/composables/__tests__/useItems.test.ts — 資料載入（契約 v2：分類分檔 + lazy 載入；mock global.fetch）
// v2 架構：fetch api/index.json（categories[] 目錄 + crawled_at，無 latest_file）
//   → 預設載入第一個分類（依 categories 順序）→ loadCategory(id) 快取命中不重複 fetch
//   → loadAll() 逐分類併發載入（itemId→categoryId 前端對照）→ 分類檔 URL 帶 ?v=crawled_at 快取穿透。
// ⚠️ useItems 為 module-level 單例（004 §2.3）→ 每個測試前以 __resetItemsShared() 重置。
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { ref } from "vue"
import { useItems, useTrend, parseItemsFile, parseIndex, parseTrendFile, ParseError, __resetItemsShared } from "@/composables/useItems"
import { matchesCondition } from "@/utils/specFilter"
import { makeItemsFile } from "@/testing/fixtures"
import type { ItemsFile } from "@/types/item"

const DAY = 86_400_000
const INDEX_MARK = "api/index.json"
const TRENDS_MARK = "api/trends/"
const CRAWLED_AT = "2026-08-16T06:00:00.000Z"

// 三個分類（依 categories 順序：第一 = 預設選中）
const CATS = [
  { id: "c4", name: "CPU", file: "api/items/g4.json", count: 2 },
  { id: "c12", name: "顯示卡", file: "api/items/g12.json", count: 1 },
  { id: "c6", name: "記憶體", file: "api/items/g6.json", count: 1 },
]
// 分類檔內容：**純陣列**（每筆無 category；history compact [d,p] ≤2 點）
const CPU_ITEMS = [
  { id: "cpu-1", name: "CPU A", spec: { cores: 8 }, history: [["2026-08-15", 8000]] },
  { id: "cpu-2", name: "CPU B", spec: {}, history: [["2026-08-14", 9000], ["2026-08-15", 9000]] },
]
const GPU_ITEMS = [
  { id: "gpu-1", name: "GPU A", spec: { vram_gb: 12 }, history: [["2026-08-15", 18990]] },
]
const RAM_ITEMS = [
  { id: "ram-1", name: "RAM A", spec: { ram_gb: 32 }, history: [] },
]

beforeEach(() => {
  __resetItemsShared() // 每測試獨立單例
})

function okResponse(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as unknown as Response
}
function failResponse(status: number): Response {
  return { ok: false, status, json: async () => ({}) } as unknown as Response
}
function badJsonResponse(): Response {
  return {
    ok: true,
    status: 200,
    json: async () => {
      throw new SyntaxError("Unexpected token")
    },
  } as unknown as Response
}

/** index.json（v2 契約）回應：categories + crawled_at（無 latest_file） */
function indexResponse(categories = CATS, crawledAt = CRAWLED_AT): Response {
  return okResponse({
    generated_at: "2026-08-17T05:00:00Z",
    source: "https://www.coolpc.com.tw/m/m-list.php",
    description: "原價屋商品價格追蹤資料 API",
    crawled_at: crawledAt,
    status: "ok",
    total: 4,
    counts: Object.fromEntries(categories.map(c => [c.name, c.count])),
    categories,
    daily_files: [{ file: "20260816.json", url: "api/daily/20260816.json", records: 4 }],
    trends_prefix: "api/trends/",
  })
}

/** 依 URL 派送回應的 fetch stub（fetch 被 useItems await，回傳 Promise<Response>）
 *  handler 可回傳 Response 或 Promise<Response>（測試延遲響應用） */
function stubFetch(handler: (url: string) => Response | Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => handler(url)))
}

/** 依檔案名派送分類檔回應（v2：api/items/{file}?v=...）
 *  files: Record<file, Response>；未列出 → 404。 */
function itemsHandler(files: Record<string, Response>): (url: string) => Response {
  return (url: string) => {
    if (url.includes(INDEX_MARK)) return indexResponse()
    const m = url.match(/api\/items\/([^?]+)(?:\?v=.*)?$/)
    if (m && files[m[1]]) return files[m[1]]
    return failResponse(404)
  }
}

/** 等待 useItems 內部的 async load 完成 */
async function flush() {
  await Promise.resolve()
  await Promise.resolve()
  await new Promise(r => setTimeout(r, 0))
}

function collectUrls(): string[] {
  const urls: string[] = []
  const f = vi.fn(async (url: string) => {
    urls.push(url)
    return failResponse(404)
  })
  vi.stubGlobal("fetch", f)
  return urls
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("useItems（v2：index → 分類 lazy 載入）", () => {
  it("bootstrap：僅載入第一分類（依 categories 順序）、URL 帶 ?v=crawled_at、meta/active 就緒", async () => {
    const urls: string[] = []
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      urls.push(url)
      return itemsHandler({ "g4.json": okResponse(CPU_ITEMS), "g12.json": okResponse(GPU_ITEMS), "g6.json": okResponse(RAM_ITEMS) })(url)
    }))
    const s = useItems()
    expect(s.loading.value).toBe(true) // 建立即載入
    await flush()
    expect(s.loading.value).toBe(false)
    expect(s.error.value).toBeNull()
    // 兩段式順序：index → 第一個分類檔（g4）；未載入其餘分類（lazy）
    expect(urls[0]).toContain(INDEX_MARK)
    expect(urls[1]).toContain(`api/items/g4.json?v=`)
    expect(urls[1]).toContain(encodeURIComponent(CRAWLED_AT)) // 快取穿透參數
    expect(urls.length).toBe(2)
    expect(s.categories.value).toEqual(CATS)
    expect(s.meta.value?.crawled_at).toBe(CRAWLED_AT)
    expect(s.activeCategoryId.value).toBe("c4") // 預設選中第一個分類
    expect(s.items.value.length).toBe(2) // 僅 CPU 分類商品
    expect(s.itemToCategory.value.get("cpu-1")).toBe("c4")
  })

  it("loadCategory：切換分類 → 抓該檔並聚合；快取命中 → 不重複 fetch", async () => {
    const urls = collectUrls()
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      urls.push(url)
      return itemsHandler({ "g4.json": okResponse(CPU_ITEMS), "g12.json": okResponse(GPU_ITEMS), "g6.json": okResponse(RAM_ITEMS) })(url)
    }))
    const s = useItems()
    await flush()
    await s.loadCategory("c12") // lazy 補載顯示卡
    await flush()
    expect(s.activeCategoryId.value).toBe("c12")
    expect(s.items.value.length).toBe(3)
    expect(s.itemToCategory.value.get("gpu-1")).toBe("c12")
    const fetchesAfterGpu = urls.length

    await s.loadCategory("c12") // 快取命中 → 無新 fetch
    await flush()
    expect(urls.length).toBe(fetchesAfterGpu)

    await s.loadCategory("c4") // 已載過 → 立即切換，無新 fetch
    await flush()
    expect(s.activeCategoryId.value).toBe("c4")
    expect(urls.length).toBe(fetchesAfterGpu)
  })

  it("loadAll：切至全部視圖、併發載入剩餘分類、itemId→categoryId 對照完整、error=null", async () => {
    const urls = collectUrls()
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      urls.push(url)
      return itemsHandler({ "g4.json": okResponse(CPU_ITEMS), "g12.json": okResponse(GPU_ITEMS), "g6.json": okResponse(RAM_ITEMS) })(url)
    }))
    const s = useItems()
    await flush()
    await s.loadAll()
    await flush()
    expect(s.activeCategoryId.value).toBeNull() // 全部視圖
    expect(urls.some(u => u.includes("g12.json?v="))).toBe(true)
    expect(urls.some(u => u.includes("g6.json?v="))).toBe(true)
    expect(s.items.value.length).toBe(4)
    expect(s.loadedIds.value.has("c4")).toBe(true)
    expect(s.loadedIds.value.has("c12")).toBe(true)
    expect(s.loadedIds.value.has("c6")).toBe(true)
    expect(s.itemToCategory.value.get("ram-1")).toBe("c6")
    expect(s.error.value).toBeNull()
  })

  it("loadAll 部分失敗：成功分類照常顯示、error='fetch'；retry 補載失敗分類", async () => {
    let g6Calls = 0
    stubFetch(url => {
      if (url.includes(INDEX_MARK)) return indexResponse()
      if (url.includes("g6.json")) {
        g6Calls += 1
        if (g6Calls === 1) return failResponse(404)
        return okResponse(RAM_ITEMS)
      }
      if (url.includes("g4.json")) return okResponse(CPU_ITEMS)
      if (url.includes("g12.json")) return okResponse(GPU_ITEMS)
      return failResponse(404)
    })
    const s = useItems()
    await flush()
    await s.loadAll()
    await flush()
    expect(s.error.value).toBe("fetch") // 聚合錯誤保留
    expect(s.items.value.length).toBe(3) // cpu + gpu 成功
    expect(s.loadedIds.value.has("c6")).toBe(false)

    await s.retry() // 重試 → 補載 g6
    await flush()
    expect(s.error.value).toBeNull()
    expect(s.loadedIds.value.has("c6")).toBe(true)
    expect(s.items.value.length).toBe(4)
  })

  it("index 404 → error='fetch'、items 為空、無分類目錄", async () => {
    stubFetch(() => failResponse(404))
    const s = useItems()
    await flush()
    expect(s.error.value).toBe("fetch")
    expect(s.items.value).toEqual([])
    expect(s.categories.value).toEqual([])
    expect(s.loading.value).toBe(false)
  })

  it("index 壞 JSON（SyntaxError）→ error='parse'", async () => {
    stubFetch(url => (url.includes(INDEX_MARK) ? badJsonResponse() : okResponse(CPU_ITEMS)))
    const s = useItems()
    await flush()
    expect(s.error.value).toBe("parse")
  })

  it("index shape 缺 categories / 缺 crawled_at → error='parse'", async () => {
    stubFetch(() => okResponse({ crawled_at: CRAWLED_AT }))
    const a = useItems()
    await flush()
    expect(a.error.value).toBe("parse")

    __resetItemsShared()
    stubFetch(() => okResponse({ categories: CATS }))
    const b = useItems()
    await flush()
    expect(b.error.value).toBe("parse")
  })

  it("第一分類檔 404 → error='fetch'（index 成功）", async () => {
    stubFetch(url => (url.includes(INDEX_MARK) ? indexResponse() : failResponse(404)))
    const s = useItems()
    await flush()
    expect(s.error.value).toBe("fetch")
    expect(s.items.value).toEqual([])
  })

  it("分類檔壞 JSON → error='parse'", async () => {
    stubFetch(url => {
      if (url.includes(INDEX_MARK)) return indexResponse()
      if (url.includes("g4.json")) return badJsonResponse()
      return failResponse(404)
    })
    const s = useItems()
    await flush()
    expect(s.error.value).toBe("parse")
  })

  it("分類檔 shape 異常（純陣列內 item 缺 id）→ error='parse'", async () => {
    stubFetch(url => {
      if (url.includes(INDEX_MARK)) return indexResponse()
      if (url.includes("g4.json")) return okResponse([{ name: "無 id 商品" }])
      return failResponse(404)
    })
    const s = useItems()
    await flush()
    expect(s.error.value).toBe("parse")
  })

  it("retry：index 失敗後重試成功 → 目錄就緒＋第一分類載入、error 清空", async () => {
    let indexCalls = 0
    stubFetch(url => {
      if (url.includes(INDEX_MARK)) {
        indexCalls += 1
        if (indexCalls === 1) return failResponse(404)
        return indexResponse()
      }
      if (url.includes("g4.json")) return okResponse(CPU_ITEMS)
      return failResponse(404)
    })
    const s = useItems()
    await flush()
    expect(s.error.value).toBe("fetch")
    await s.retry()
    await flush()
    expect(s.error.value).toBeNull()
    expect(s.categories.value.length).toBe(3)
    expect(s.items.value.length).toBe(2)
  })

  it("crawled_at 8 天前 → isStale=true；7 天內 → false", async () => {
    const old = new Date(Date.now() - 8 * DAY).toISOString()
    stubFetch(url => (url.includes(INDEX_MARK) ? indexResponse(CATS, old) : failResponse(404)))
    const stale = useItems()
    await flush()
    expect(stale.isStale.value).toBe(true)

    __resetItemsShared()
    const fresh = new Date(Date.now() - 7 * DAY).toISOString()
    stubFetch(url => (url.includes(INDEX_MARK) ? indexResponse(CATS, fresh) : failResponse(404)))
    const ok = useItems()
    await flush()
    expect(ok.isStale.value).toBe(false)
  })

  it("單例共享：第二次 useItems() 回傳同一實例（不重複 fetch，004 §2.3）", async () => {
    stubFetch(itemsHandler({ "g4.json": okResponse(CPU_ITEMS) }))
    const a = useItems()
    await flush()
    const b = useItems()
    expect(b).toBe(a)
    expect(b.items.value).toBe(a.items.value)
    expect(b.loading.value).toBe(false)
  })

  it("isLoadingCategory：特定分類載入中為 true、完成後 false", async () => {
    const resolver: { fn: (() => void) | null } = { fn: null }
    stubFetch(url => {
      if (url.includes(INDEX_MARK)) return indexResponse()
      if (url.includes("g12.json")) {
        return new Promise<Response>(resolve => {
          resolver.fn = () => resolve(okResponse(GPU_ITEMS))
        })
      }
      if (url.includes("g4.json")) return okResponse(CPU_ITEMS)
      return failResponse(404)
    })
    const s = useItems()
    await flush()
    const p = s.loadCategory("c12")
    await Promise.resolve()
    expect(s.isLoadingCategory("c12")).toBe(true)
    resolver.fn?.()
    await p
    await flush()
    expect(s.isLoadingCategory("c12")).toBe(false)
  })
})

describe("useTrend（O4：api/trends/{id}.json 完整歷史）", () => {
  it("成功載入：fetch trends/{id}.json → compact history 正規化為 PricePoint[]、loading=false、error=null", async () => {
    const urls: string[] = []
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      urls.push(url)
      if (url.includes(TRENDS_MARK) && url.includes("/c1.json")) {
        return okResponse({ id: "c1", history: [["2026-08-10", 12000], ["2026-08-12", 11000], ["2026-08-15", 9990]] })
      }
      return failResponse(404)
    }))
    const { history, loading, error } = useTrend("c1")
    await flush()
    expect(urls[0]).toContain("api/trends/c1.json")
    expect(history.value).toEqual([
      { d: "2026-08-10", p: 12000 },
      { d: "2026-08-12", p: 11000 },
      { d: "2026-08-15", p: 9990 },
    ])
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it("404 → error='fetch'、history=[]（不 throw）", async () => {
    stubFetch(() => failResponse(404))
    const { history, error, loading } = useTrend("nonexistent")
    await flush()
    expect(error.value).toBe("fetch")
    expect(history.value).toEqual([])
    expect(loading.value).toBe(false)
  })

  it("壞 JSON（SyntaxError）→ error='parse'、history=[]", async () => {
    stubFetch(() => badJsonResponse())
    const { history, error } = useTrend("c1")
    await flush()
    expect(error.value).toBe("parse")
    expect(history.value).toEqual([])
  })

  it("shape 不符（缺 history ／缺 id）→ error='parse'", async () => {
    stubFetch(() => okResponse({ id: "c1" }))
    const a = useTrend("c1")
    await flush()
    expect(a.error.value).toBe("parse")

    vi.stubGlobal("fetch", vi.fn(async () => okResponse({ history: [["2026-08-15", 9990]] })))
    const b = useTrend("c2")
    await flush()
    expect(b.error.value).toBe("parse")
  })

  it("id 為 ref：變化自動重新載入新 URL", async () => {
    const id = ref("c1")
    const urls: string[] = []
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      urls.push(url)
      const m = url.match(/api\/trends\/([^/]+)\.json/)
      return okResponse({ id: m?.[1] ?? "", history: [["2026-08-15", 9990]] })
    }))
    const { history } = useTrend(id)
    await flush()
    expect(urls).toEqual([expect.stringContaining("api/trends/c1.json")])
    id.value = "c2"
    await flush()
    expect(urls).toEqual([
      expect.stringContaining("api/trends/c1.json"),
      expect.stringContaining("api/trends/c2.json"),
    ])
    expect(history.value).toEqual([{ d: "2026-08-15", p: 9990 }])
  })

  it("id 為 undefined／空字串 → 不 fetch、空歷史、error=null", async () => {
    const fetches: string[] = []
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      fetches.push(url)
      return failResponse(404)
    }))
    const { history, loading, error } = useTrend(ref<string | undefined>(undefined))
    await flush()
    expect(fetches).toEqual([])
    expect(history.value).toEqual([])
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it("retry：首次 404 後重試成功 → error 清空、history 填入", async () => {
    let calls = 0
    stubFetch(url => {
      if (!url.includes(TRENDS_MARK)) return failResponse(404)
      calls += 1
      if (calls === 1) return failResponse(404)
      return okResponse({ id: "c1", history: [["2026-08-15", 9990]] })
    })
    const { error, retry, history } = useTrend("c1")
    await flush()
    expect(error.value).toBe("fetch")
    await retry()
    await flush()
    expect(error.value).toBeNull()
    expect(history.value).toEqual([{ d: "2026-08-15", p: 9990 }])
  })
})

describe("parseTrendFile（純函數）", () => {
  it("非 object → ParseError", () => {
    expect(() => parseTrendFile(null)).toThrow(ParseError)
    expect(() => parseTrendFile([])).toThrow(ParseError)
  })

  it("缺 id / id 非字串 → ParseError", () => {
    expect(() => parseTrendFile({ history: [] })).toThrow(ParseError)
    expect(() => parseTrendFile({ id: "", history: [] })).toThrow(ParseError)
    expect(() => parseTrendFile({ id: 3, history: [] })).toThrow(ParseError)
  })

  it("history 非陣列／點格式不符 → ParseError", () => {
    expect(() => parseTrendFile({ id: "c1", history: "x" })).toThrow(ParseError)
    expect(() => parseTrendFile({ id: "c1", history: [["2026-08-15"]] })).toThrow(ParseError)
    expect(() => parseTrendFile({ id: "c1", history: [["2026-08-15", "9990"]] })).toThrow(ParseError)
  })

  it("空 history → history=[]（新商品尚無價格紀錄）", () => {
    expect(parseTrendFile({ id: "c1", history: [] })).toEqual({ id: "c1", history: [] })
  })

  it("compact [d,p] → PricePoint[]（升冪原樣保留）", () => {
    expect(parseTrendFile({ id: "c1", history: [["2026-08-14", 10500], ["2026-08-15", 9990]] })).toEqual({
      id: "c1",
      history: [
        { d: "2026-08-14", p: 10500 },
        { d: "2026-08-15", p: 9990 },
      ],
    })
  })
})

describe("parseIndex（v2 純函數）", () => {
  it("非 object → ParseError", () => {
    expect(() => parseIndex(null)).toThrow(ParseError)
    expect(() => parseIndex([])).toThrow(ParseError)
  })

  it("categories 缺失 / 非陣列 → ParseError", () => {
    expect(() => parseIndex({ crawled_at: CRAWLED_AT })).toThrow(ParseError)
    expect(() => parseIndex({ crawled_at: CRAWLED_AT, categories: "x" })).toThrow(ParseError)
  })

  it("categories 元素缺 id / file → ParseError", () => {
    expect(() => parseIndex({ crawled_at: CRAWLED_AT, categories: [{ name: "CPU", file: "g4.json" }] })).toThrow(ParseError)
    expect(() => parseIndex({ crawled_at: CRAWLED_AT, categories: [{ id: "c4", name: "CPU" }] })).toThrow(ParseError)
  })

  it("crawled_at 缺失 / 非字串 → ParseError", () => {
    expect(() => parseIndex({ categories: CATS })).toThrow(ParseError)
    expect(() => parseIndex({ categories: CATS, crawled_at: 3 })).toThrow(ParseError)
    expect(() => parseIndex({ categories: CATS, crawled_at: "" })).toThrow(ParseError)
  })

  it("合法 v2 index → 回傳 categories/crawledAt/source/total（count 缺省補 0）", () => {
    const parsed = parseIndex({
      crawled_at: CRAWLED_AT,
      source: "https://coolpc.com.tw",
      total: 4,
      categories: [{ id: "c4", name: "CPU", file: "g4.json" }],
    })
    expect(parsed.crawledAt).toBe(CRAWLED_AT)
    expect(parsed.source).toBe("https://coolpc.com.tw")
    expect(parsed.total).toBe(4)
    expect(parsed.categories).toEqual([{ id: "c4", name: "CPU", file: "g4.json", count: 0 }])
  })
})

describe("parseItemsFile（v2 純函數）", () => {
  it("非 object 非陣列 → ParseError", () => {
    expect(() => parseItemsFile(null)).toThrow(ParseError)
    expect(() => parseItemsFile("x")).toThrow(ParseError)
  })

  it("v2 純陣列（頂層 array、無 category 欄位）→ Item[]，compact history 正規化", () => {
    const parsed = parseItemsFile([
      { id: "a1", name: "某 CPU", spec: { cores: 8 }, history: [["2026-08-14", 10000], ["2026-08-15", 10500]] },
      { id: "a2", name: "某卡", spec: {}, status: "gone" },
    ], { crawledAt: CRAWLED_AT })
    expect(parsed.meta.crawled_at).toBe(CRAWLED_AT)
    expect(parsed.items[0].history).toEqual([
      { d: "2026-08-14", p: 10000 },
      { d: "2026-08-15", p: 10500 },
    ])
    expect(parsed.items[1].status).toBe("gone")
    expect(parsed.items[0]).not.toHaveProperty("category") // v2：無 category
  })

  it("v2 純陣列未注入 crawledAt → 相容（meta.crawled_at=''，不拋）", () => {
    const parsed = parseItemsFile([{ id: "a1", name: "某商品", history: [] }])
    expect(parsed.meta.crawled_at).toBe("")
    expect(parsed.items.length).toBe(1)
  })

  it("v2 純陣列 item 缺 id/name → ParseError", () => {
    expect(() => parseItemsFile([{ name: "no id" }], { crawledAt: CRAWLED_AT })).toThrow(ParseError)
    expect(() => parseItemsFile([{ id: "x" }], { crawledAt: CRAWLED_AT })).toThrow(ParseError)
  })

  it("舊 002 版本化快照形狀 {crawled_at, items} 相容（v1 category 欄位被忽略）", () => {
    const parsed = parseItemsFile({
      crawled_at: "2026-08-15T06:00:00Z",
      items: [
        { id: "a1", category: "CPU", name: "某 CPU", history: [["2026-08-15", 9990]] },
      ],
    })
    expect(parsed.meta.crawled_at).toBe("2026-08-15T06:00:00Z")
    expect(parsed.meta.source).toBe("")
    expect(parsed.items[0].history).toEqual([{ d: "2026-08-15", p: 9990 }])
    expect(parsed.items[0]).not.toHaveProperty("category") // v2 型別無 category
  })

  it("舊 001 形狀 {meta:{crawled_at,source}, items} 相容", () => {
    const parsed = parseItemsFile({
      meta: { crawled_at: "2026-08-15T06:00:00Z", source: "s" },
      items: [{ id: "a1", name: "某商品", history: [] }],
    })
    expect(parsed.meta.crawled_at).toBe("2026-08-15T06:00:00Z")
    expect(parsed.meta.source).toBe("s")
  })

  it("舊形狀 items 非陣列 → ParseError", () => {
    expect(() => parseItemsFile({ meta: { crawled_at: "x" }, items: "nope" })).toThrow(ParseError)
  })

  it("舊形狀缺 meta.crawled_at → ParseError", () => {
    expect(() => parseItemsFile({ items: [] })).toThrow(ParseError)
  })

  it("真資料 spec 形狀 {brand, model, extra:{...}} 平鋪為前端 ItemSpec（篩選/表格可用）", () => {
    const parsed = parseItemsFile([
      {
        id: "g1",
        name: "技嘉 RTX3060 WINDFORCE OC 12G",
        spec: {
          brand: "技嘉",
          model: "RTX3060 WINDFORCE OC 12G",
          extra: { vram_gb: 12, chip: "RTX 3060", interface: "PCIe 4.0", length_mm: 198 },
        },
        history: [["2026-08-15", 7990]],
      },
      {
        id: "g2",
        name: "無品牌未解析卡",
        spec: { brand: null, model: null, extra: {} }, // spec_parser 最少欄位
        history: [["2026-08-15", 5990]],
      },
      {
        id: "r1",
        name: "UMAX 單條32GB DDR5-4800/CL40",
        spec: {
          brand: "UMAX",
          model: "單條32GB DDR5-4800/CL40",
          extra: { ram_gb: 32, spec: "DDR5", clock_mhz: 4800 }, // extra 含 spec 鍵
        },
        history: [["2026-08-15", 10900]],
      },
    ], { crawledAt: CRAWLED_AT })
    expect(parsed.items[0].spec).toEqual({
      brand: "技嘉",
      model: "RTX3060 WINDFORCE OC 12G",
      vram_gb: 12,
      chip: "RTX 3060",
      interface: "PCIe 4.0",
      length_mm: 198,
    })
    expect(parsed.items[0].spec.extra).toBeUndefined() // 巢狀 extra 鍵移除
    expect(parsed.items[1].spec).toEqual({}) // null 值剔除（最少欄位商品）
    expect(parsed.items[2].spec).toEqual({ brand: "UMAX", model: "單條32GB DDR5-4800/CL40", ram_gb: 32, spec: "DDR5", clock_mhz: 4800 })
    expect(matchesCondition(parsed.items[0], { id: "vram_gb-12", field: "vram_gb", type: "number", op: ">=", value: 12, label: "VRAM≥12G", unit: "G" })).toBe(true)
  })

  it("缺 history / spec 的舊資料補預設值（[] / {}），下游不崩潰", () => {
    const parsed = parseItemsFile([{ id: "a2", name: "舊商品", status: "gone" }], { crawledAt: CRAWLED_AT })
    expect(parsed.items[0].history).toEqual([])
    expect(parsed.items[0].spec).toEqual({})
    expect(parsed.items[0].status).toBe("gone")
  })

  it("history 點格式不符 → ParseError", () => {
    expect(() => parseItemsFile([{ id: "a1", name: "x", history: [["2026-08-15"]] }], { crawledAt: CRAWLED_AT })).toThrow(ParseError)
    expect(() => parseItemsFile([{ id: "a1", name: "x", history: [["2026-08-15", "9990"]] }], { crawledAt: CRAWLED_AT })).toThrow(ParseError)
  })

  it("單筆缺 name（舊形狀）→ ParseError", () => {
    const doc = makeItemsFile() as unknown as ItemsFile
    const raw = { meta: doc.meta, items: [{ id: "x", category: "CPU" }] }
    expect(() => parseItemsFile(raw)).toThrow(ParseError)
  })
})