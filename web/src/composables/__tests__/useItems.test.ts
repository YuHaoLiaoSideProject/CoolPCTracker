// web/src/composables/__tests__/useItems.test.ts — 資料載入（mock global.fetch）
// （開發規格 003 §2.4：成功/404/壞 JSON/shape/compact 正規化/isStale/retry）
// ⚠️ useItems 為 module-level 單例（004 §2.3：003/004 共用同一份資料，避免重複請求）
//   → 每個測試前以 __resetItemsShared() 重置，讓各測試以獨立 stub fetch 驗證。
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { useItems, parseItemsFile, ParseError, __resetItemsShared } from "@/composables/useItems"
import { matchesCondition } from "@/utils/specFilter"
import { makeItemsFile } from "@/testing/fixtures"
import type { ItemsFile } from "@/types/item"

const DAY = 86_400_000

beforeEach(() => {
  __resetItemsShared() // 每測試獨立單例
})

function okResponse(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as unknown as Response
}
function failResponse(status: number): Response {
  return { ok: false, status, json: async () => ({}) } as unknown as Response
}

function stubFetch(impl: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(impl))
}

/** 等待 useItems 內部的 async load() 完成 */
async function flush() {
  await Promise.resolve()
  await Promise.resolve()
  await new Promise(r => setTimeout(r, 0))
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("useItems", () => {
  it("成功載入：items + meta 就緒、error 為 null", async () => {
    const doc = makeItemsFile()
    stubFetch(async () => okResponse(doc))
    const { items, meta, loading, error } = useItems()
    await flush()
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
    expect(items.value.length).toBe(doc.items.length)
    expect(meta.value?.crawled_at).toBe(doc.meta.crawled_at)
  })

  it("HTTP 404 → error='fetch'、items 為空", async () => {
    stubFetch(async () => failResponse(404))
    const { items, error, loading } = useItems()
    await flush()
    expect(error.value).toBe("fetch")
    expect(items.value).toEqual([])
    expect(loading.value).toBe(false)
  })

  it("壞 JSON（SyntaxError）→ error='parse'", async () => {
    stubFetch(async () => ({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError("Unexpected token")
      },
    }) as unknown as Response)
    const { error } = useItems()
    await flush()
    expect(error.value).toBe("parse")
  })

  it("shape 缺欄位 → error='parse'", async () => {
    stubFetch(async () => okResponse({ meta: { crawled_at: "x" }, items: [{ id: 1 }] }))
    const { error } = useItems()
    await flush()
    expect(error.value).toBe("parse")
  })

  it("compact history 正規化為 PricePoint {d, p}", async () => {
    const doc = makeItemsFile({
      items: [
        {
          id: "a1",
          category: "顯示卡",
          name: "某卡",
          spec: {},
          status: "in_stock",
          first_seen: "2026-08-01",
          last_seen: "2026-08-15",
          history: [
            ["2026-08-14", 10000],
            ["2026-08-15", 10500],
          ],
        },
      ],
    })
    stubFetch(async () => okResponse(doc))
    const { items } = useItems()
    await flush()
    expect(items.value[0].history).toEqual([
      { d: "2026-08-14", p: 10000 },
      { d: "2026-08-15", p: 10500 },
    ])
  })

  it("缺 history / spec 的舊資料補預設值（[] / {}），下游不崩潰", async () => {
    const doc = makeItemsFile({
      items: [
        {
          id: "a2",
          category: "SSD",
          name: "舊商品",
          status: "gone",
          first_seen: "2026-07-01",
          last_seen: "2026-07-10",
        },
      ],
    })
    stubFetch(async () => okResponse(doc))
    const { items } = useItems()
    await flush()
    expect(items.value[0].history).toEqual([])
    expect(items.value[0].spec).toEqual({})
    expect(items.value[0].status).toBe("gone")
  })

  it("crawled_at 8 天前 → isStale=true；7 天內 → false", async () => {
    const doc8 = makeItemsFile({ meta: { crawled_at: new Date(Date.now() - 8 * DAY).toISOString(), source: "t" } })
    stubFetch(async () => okResponse(doc8))
    const stale = useItems()
    await flush()
    expect(stale.isStale.value).toBe(true)

    __resetItemsShared() // 換新單例驗證「7 天內不視為過期」
    const doc7 = makeItemsFile({ meta: { crawled_at: new Date(Date.now() - 7 * DAY).toISOString(), source: "t" } })
    stubFetch(async () => okResponse(doc7))
    const fresh = useItems()
    await flush()
    expect(fresh.isStale.value).toBe(false)
  })

  it("單例共享：第二次 useItems() 回傳同一實例（不重複 fetch，004 §2.3）", async () => {
    stubFetch(async () => okResponse(makeItemsFile()))
    const a = useItems()
    await flush()
    const b = useItems() // 同單例：不重新 fetch、不重新 loading
    expect(b).toBe(a)
    expect(b.items.value).toBe(a.items.value)
    expect(b.loading.value).toBe(false)
  })

  it("retry：失敗後重試成功 → error 清空、items 填入", async () => {
    let calls = 0
    stubFetch(async () => {
      calls += 1
      if (calls === 1) return failResponse(404)
      return okResponse(makeItemsFile())
    })
    const { error, retry, items } = useItems()
    await flush()
    expect(error.value).toBe("fetch")
    await retry()
    await flush()
    expect(error.value).toBeNull()
    expect(items.value.length).toBeGreaterThan(0)
  })
})

describe("parseItemsFile（純函數）", () => {
  it("非 object → ParseError", () => {
    expect(() => parseItemsFile(null)).toThrow(ParseError)
    expect(() => parseItemsFile([])).toThrow(ParseError)
  })

  it("002 版本化快照形狀 {crawled_at, items}（頂層無 meta）亦相容（§1.7 合約）", () => {
    const parsed = parseItemsFile({
      crawled_at: "2026-08-15T06:00:00Z",
      items: [
        { id: "a1", category: "CPU", name: "某 CPU", history: [["2026-08-15", 9990]] },
      ],
    })
    expect(parsed.meta.crawled_at).toBe("2026-08-15T06:00:00Z")
    expect(parsed.meta.source).toBe("")
    expect(parsed.items[0].history).toEqual([{ d: "2026-08-15", p: 9990 }])
  })

  it("items 非陣列 → ParseError", () => {
    expect(() => parseItemsFile({ meta: { crawled_at: "x" }, items: "nope" })).toThrow(ParseError)
  })

  it("缺 meta.crawled_at → ParseError", () => {
    expect(() => parseItemsFile({ items: [] })).toThrow(ParseError)
  })

  it("真資料 spec 形狀 {brand, model, extra:{...}} 平鋪為前端 ItemSpec（篩選/表格可用）", () => {
    const parsed = parseItemsFile({
      crawled_at: "2026-08-15T06:00:00Z",
      items: [
        {
          id: "g1",
          category: "顯示卡",
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
          category: "顯示卡",
          name: "無品牌未解析卡",
          spec: { brand: null, model: null, extra: {} }, // spec_parser 最少欄位
          history: [["2026-08-15", 5990]],
        },
        {
          id: "r1",
          category: "記憶體",
          name: "UMAX 單條32GB DDR5-4800/CL40",
          spec: {
            brand: "UMAX",
            model: "單條32GB DDR5-4800/CL40",
            extra: { capacity_gb: 32, spec: "DDR5", clock_mhz: 4800 }, // extra 含 spec 鍵
          },
          history: [["2026-08-15", 10900]],
        },
      ],
    })
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
    expect(parsed.items[2].spec).toEqual({ brand: "UMAX", model: "單條32GB DDR5-4800/CL40", capacity_gb: 32, spec: "DDR5", clock_mhz: 4800 })
    expect(matchesCondition(parsed.items[0], { id: "vram_gb-12", field: "vram_gb", op: ">=", value: 12, label: "VRAM≥12G", unit: "G" })).toBe(true)
  })

  it("單筆缺 name → ParseError", () => {
    const doc = makeItemsFile() as unknown as ItemsFile
    const raw = { meta: doc.meta, items: [{ id: "x", category: "CPU" }] }
    expect(() => parseItemsFile(raw)).toThrow(ParseError)
  })
})
