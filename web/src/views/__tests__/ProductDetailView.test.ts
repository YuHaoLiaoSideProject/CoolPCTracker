// web/src/views/__tests__/ProductDetailView.test.ts — 四態狀態機＋目標價互動（BDD E3/E4/E5/E6/E7/E8/E13）
// mock useItems（003 契約）與 useTrend（O4：完整歷史來自 api/trends/{id}.json）與
// PriceTrendChart（jsdom 無 canvas）；用 memory router 直接進 /product/:id。
// 資料形狀（O4）：列表 state 的 item.history 僅 ≤2 點（漲跌徽章用）；
// 趨勢圖與歷史最低價改由 useTrend 的完整 history 提供。
import { describe, expect, it, vi, beforeEach } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import { createRouter, createMemoryHistory } from "vue-router"
import type { Item, PricePoint } from "@/types/item"

vi.mock("@/composables/useItems", async () => {
  const { ref } = await import("vue")
  // factory 閉包內建立一次 → 每次 useItems()/useTrend() 回傳同一組 ref（單例共享語義）
  const items = ref<Item[]>([])
  const meta = ref<{ crawled_at: string; source: string } | null>(null)
  const loading = ref(true)
  const error = ref<"fetch" | "parse" | null>(null)
  const retry = vi.fn()
  const isStale = ref(false)
  // 契約 v2：分類目錄 + 外部對照（lazy 載入）
  const categories = ref<{ id: string; name: string; file: string; count: number }[]>([
    { id: "cpu", name: "CPU", file: "g4.json", count: 1 },
  ])
  const activeCategoryId = ref<string | null>(null)
  const itemToCategory = ref<Map<string, string>>(new Map([["3f9a1c2b8e4d5f6a", "cpu"]]))
  const loadedIds = ref<Set<string>>(new Set())
  const loadCategory = vi.fn(async () => {})
  const loadAll = vi.fn(async () => {})
  const isLoadingCategory = () => false
  // O4：trends 狀態（history 由測試依商品設定；loading/error 模擬獨立載入）
  const trendHistory = ref<PricePoint[]>([])
  const trendLoading = ref(false)
  const trendError = ref<"fetch" | "parse" | null>(null)
  const trendRetry = vi.fn()
  return {
    useItems: () => ({
      items, meta, loading, error, retry, isStale,
      categories, activeCategoryId, itemToCategory, loadedIds,
      loadCategory, loadAll, isLoadingCategory,
    }),
    useTrend: () => ({ history: trendHistory, loading: trendLoading, error: trendError, retry: trendRetry }),
  }
})

vi.mock("@/components/PriceTrendChart.vue", () => ({
  default: {
    name: "PriceTrendChartStub",
    props: ["history", "targetPrice", "yMin", "yMax"],
    template: '<div class="chart-stub" />',
  },
}))

import { useItems, useTrend } from "@/composables/useItems"
import ProductDetailView from "@/views/ProductDetailView.vue"

// mock 的 useItems / useTrend 每次回傳同一組 ref（同 factory 閉包 → 單例共享語義）
const state = (): ReturnType<typeof useItems> => useItems()
const trendState = (): ReturnType<typeof useTrend> => useTrend("") // mock 忽略 id，回傳共用狀態

const base: Omit<Item, "id" | "name"> = {
  // 契約 v2：Item 無 category 欄位（分類為外部狀態）
  spec: { brand: "Intel", cores: 14, socket: "LGA1700" },
  status: "in_stock",
  first_seen: "2026-08-13",
  last_seen: "2026-08-15",
  history: [],
}
// O4：列表快照 history 僅最近 ≤2 點（此處 08-14→08-15，跌 510）
const i5 = (): Item => ({
  ...base,
  id: "3f9a1c2b8e4d5f6a",
  name: "Intel i5-13600K",
  history: [
    { d: "2026-08-14", p: 10500 },
    { d: "2026-08-15", p: 9990 },
  ],
})
// O4：trends/{id}.json 完整歷史（低 9990 @08-15、高 11500 @08-10/11）
const I5_TREND: PricePoint[] = [
  { d: "2026-08-10", p: 11500 },
  { d: "2026-08-11", p: 11500 },
  { d: "2026-08-12", p: 11000 },
  { d: "2026-08-13", p: 10500 },
  { d: "2026-08-14", p: 10500 },
  { d: "2026-08-15", p: 9990 },
]

async function mountView(id: string, query: Record<string, string> = {}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", name: "listing", component: { template: "<div>listing-page</div>" } },
      { path: "/product/:id", name: "product-detail", component: ProductDetailView },
    ],
  })
  await router.push({ path: `/product/${encodeURIComponent(id)}`, query })
  await router.isReady()
  const w = mount(ProductDetailView, { global: { plugins: [router] } })
  return { w, router }
}

const chartStub = (w: ReturnType<typeof mount>) => w.findComponent({ name: "PriceTrendChartStub" })

beforeEach(() => {
  const s = state()
  s.items.value = []
  s.meta.value = { crawled_at: "2026-08-15T06:00:00Z", source: "test" }
  s.loading.value = false
  s.error.value = null
  ;(s.retry as unknown as ReturnType<typeof vi.fn>).mockClear()
  // O4：trends 預設（成功、空歷史）；各測試依商品設定 full history
  const t = trendState()
  t.history.value = []
  t.loading.value = false
  t.error.value = null
  ;(t.retry as unknown as ReturnType<typeof vi.fn>).mockClear()
})

describe("四態狀態機", () => {
  it("loading → skeleton（不渲染就緒內容）", async () => {
    state().loading.value = true
    const { w } = await mountView("3f9a1c2b8e4d5f6a")
    expect(w.find(".detail-skeleton").exists()).toBe(true)
    expect(w.find(".detail-title").exists()).toBe(false)
  })

  it("載入失敗（E1）→ 資料載入失敗＋重新載入；retry 被呼叫", async () => {
    state().error.value = "fetch"
    const { w } = await mountView("3f9a1c2b8e4d5f6a")
    expect(w.text()).toContain("資料載入失敗")
    await w.find(".retry-btn").trigger("click")
    expect(state().retry).toHaveBeenCalledTimes(1)
    expect(w.text()).toContain("返回列表")
  })

  it("找不到商品（E3）→ 找不到此商品＋返回列表", async () => {
    const { w } = await mountView("8a4b2c6d1e9f3a71")
    expect(w.text()).toContain("找不到此商品")
    expect(w.text()).toContain("返回列表")
  })
})

describe("就緒狀態內容（happy path）", () => {
  it("完整資訊：標題／目前價／漲跌標籤（E8 降價）/歷史最低／規格表／更新時間", async () => {
    state().items.value = [i5()]
    trendState().history.value = I5_TREND // 歷史最低取自完整趨勢
    const { w } = await mountView("3f9a1c2b8e4d5f6a")
    expect(w.find(".detail-title").text()).toContain("Intel i5-13600K")
    expect(w.find(".price-current").text()).toBe("NT$ 9,990")
    expect(w.find(".price-change").text()).toContain("降價 NT$510（-4.9%）")
    expect(w.find(".price-change--down").exists()).toBe(true) // 綠 ▼
    expect(w.find(".trend-ico").exists()).toBe(true)
    expect(w.find(".price-low").text()).toContain("NT$ 9,990")
    expect(w.find(".low-date").text()).toContain("2026-08-15")
    expect(w.findAll(".spec-key").map((n) => n.text())).toContain("核心數")
    expect(w.find(".ps-updated").text()).toContain("2026-08-15 14:00")
  })

  it("圖表收到完整趨勢 history／targetPrice／yMin／yMax props；WatchlistButton/CompareToggle 收到正確 props", async () => {
    state().items.value = [i5()]
    trendState().history.value = I5_TREND
    const { w } = await mountView("3f9a1c2b8e4d5f6a")
    const chart = chartStub(w)
    expect(chart.props("history")).toHaveLength(6) // 完整歷史（非列表的 ≤2 點）
    expect(chart.props("targetPrice")).toBeNull()
    expect(chart.props("yMin")).toBeCloseTo(9990 * 0.98)
    expect(chart.props("yMax")).toBeCloseTo(11500 * 1.02)
    const watchBtn = w.findComponent({ name: "WatchlistButton" })
    expect(watchBtn.exists()).toBe(true)
    expect(watchBtn.props("id")).toBe("3f9a1c2b8e4d5f6a")
    const compareBtn = w.findComponent({ name: "CompareToggle" })
    expect(compareBtn.exists()).toBe(true)
    expect(compareBtn.props("id")).toBe("3f9a1c2b8e4d5f6a")
  })

  it("history 空（E4）→ 目前價「—」＋尚無歷史資料＋不渲染圖表", async () => {
    state().items.value = [{ ...base, id: "empty-1", name: "新品 X", history: [] }]
    trendState().history.value = [] // 趨勢亦無資料
    const { w } = await mountView("empty-1")
    expect(w.text()).toContain("尚無歷史資料")
    expect(w.find(".price-current").text()).toBe("—")
    expect(chartStub(w).exists()).toBe(false)
  })

  it("僅一筆（E5）→ 首日追蹤，尚無漲跌比較；low=目前價", async () => {
    state().items.value = [{ ...base, id: "single-1", name: "新品 X", history: [{ d: "2026-08-15", p: 5990 }] }]
    trendState().history.value = [{ d: "2026-08-15", p: 5990 }]
    const { w } = await mountView("single-1")
    expect(w.text()).toContain("首日追蹤，尚無漲跌比較")
    expect(w.find(".price-low").text()).toContain("NT$ 5,990")
    expect(w.find(".low-date").text()).toContain("2026-08-15")
    expect(chartStub(w).exists()).toBe(true)
  })

  it("下架商品（E13）→ 此商品已下架 badge 且價格照常顯示", async () => {
    state().items.value = [{ ...base, id: "gone-1", name: "停產 Z", status: "gone", history: [{ d: "2026-08-14", p: 4490 }] }]
    trendState().history.value = [{ d: "2026-08-14", p: 4490 }]
    const { w } = await mountView("gone-1")
    expect(w.find(".badge-gone").text()).toBe("此商品已下架")
    expect(w.find(".price-current").text()).toBe("NT$ 4,490")
  })
})

describe("趨勢區塊獨立狀態（O4）", () => {
  it("trend 載入中 → 趨勢區塊顯示載入中、不渲染圖表；其餘頁面照常", async () => {
    state().items.value = [i5()]
    trendState().loading.value = true
    const { w } = await mountView("3f9a1c2b8e4d5f6a")
    expect(w.find(".trend-status").text()).toContain("趨勢資料載入中")
    expect(chartStub(w).exists()).toBe(false)
    expect(w.find(".detail-title").text()).toContain("Intel i5-13600K") // 不影響其餘頁面
    expect(w.find(".price-current").text()).toBe("NT$ 9,990")
  })

  it("trend 載入失敗（fetch）→ 錯誤＋重新載入按鈕；點擊呼叫 trend.retry；其餘頁面照常", async () => {
    state().items.value = [i5()]
    trendState().error.value = "fetch"
    const { w } = await mountView("3f9a1c2b8e4d5f6a")
    const status = w.find(".trend-status--error")
    expect(status.text()).toContain("趨勢資料載入失敗")
    expect(chartStub(w).exists()).toBe(false)
    await w.find(".trend-retry").trigger("click")
    expect(trendState().retry).toHaveBeenCalledTimes(1)
    expect(w.find(".price-summary").exists()).toBe(true) // 其餘頁面不受影響
  })

  it("trend 格式錯誤（parse）→ 趨勢區塊顯示格式錯誤文案", async () => {
    state().items.value = [i5()]
    trendState().error.value = "parse"
    const { w } = await mountView("3f9a1c2b8e4d5f6a")
    expect(w.find(".trend-status--error").text()).toContain("趨勢資料格式錯誤")
    expect(w.find(".detail-title").exists()).toBe(true)
  })

  it("trend 失敗時歷史最低退回列表短歷史（≤2 點）→ 不空白", async () => {
    state().items.value = [i5()]
    trendState().error.value = "fetch"
    const { w } = await mountView("3f9a1c2b8e4d5f6a")
    expect(w.find(".price-low").text()).toContain("NT$ 9,990") // 列表短歷史 low=9990
  })
})

describe("目標價互動（E6/E7/E12）", () => {
  async function setup() {
    state().items.value = [i5()] // 列表 history 僅 ≤2 點（10500→9990）
    trendState().history.value = I5_TREND // 歷史區間由完整趨勢決定：9990~11500
    const { w } = await mountView("3f9a1c2b8e4d5f6a")
    return w
  }

  it("套用 9500 → markLine props 生效；修改 9800 更新；清除後為 null（E12 session 級）", async () => {
    const w = await setup()
    const input = w.find(".target-input")
    await input.setValue("9500")
    await w.find(".target-form").trigger("submit")
    expect(chartStub(w).props("targetPrice")).toBe(9500)
    expect(w.find(".target-btn.ghost").exists()).toBe(true) // 清除按鈕出現

    await input.setValue("9,800")
    await w.find(".target-form").trigger("submit")
    expect(chartStub(w).props("targetPrice")).toBe(9800) // 千分位輸入亦接受

    await w.find(".target-btn.ghost").trigger("click")
    expect(chartStub(w).props("targetPrice")).toBeNull()
    expect(w.find(".target-btn.ghost").exists()).toBe(false)
  })

  it("四組驗證訊息（E6）→ 不套用 markLine＋紅框", async () => {
    const w = await setup()
    const input = w.find(".target-input")

    await input.setValue("")
    await w.find(".target-form").trigger("submit")
    expect(w.text()).toContain("請輸入目標價")

    await input.setValue("abc")
    await w.find(".target-form").trigger("submit")
    expect(w.text()).toContain("請輸入有效數字")

    await input.setValue("0")
    await w.find(".target-form").trigger("submit")
    expect(w.text()).toContain("請輸入大於 0 的有效數字")

    await input.setValue("-100")
    await w.find(".target-form").trigger("submit")
    expect(w.text()).toContain("請輸入大於 0 的有效數字")

    expect(input.classes()).toContain("is-error") // 紅框
    expect(chartStub(w).props("targetPrice")).toBeNull() // 從未套用
  })

  it("超出歷史區間（E7：9000 vs 9990~11500）→ 仍套用＋Y 軸擴展＋提示", async () => {
    const w = await setup()
    await w.find(".target-input").setValue("9000")
    await w.find(".target-form").trigger("submit")
    expect(chartStub(w).props("targetPrice")).toBe(9000)
    expect(chartStub(w).props("yMin")).toBeCloseTo(9000 * 0.98)
    expect(chartStub(w).props("yMax")).toBeCloseTo(11500 * 1.02)
    expect(w.find(".hint-out-of-range").text()).toContain("目標價超出歷史區間")
  })
})

describe("返回列表保留分類 context（§8 step 8）", () => {
  it("點返回列表 → 回 / 且 ?category= 回帶", async () => {
    state().items.value = [i5()]
    const { w, router } = await mountView("3f9a1c2b8e4d5f6a", { category: "cpu" })
    await w.find(".detail-breadcrumb a").trigger("click")
    await flushPromises()
    expect(router.currentRoute.value.path).toBe("/")
    expect(router.currentRoute.value.query.category).toBe("cpu")
  })
})
