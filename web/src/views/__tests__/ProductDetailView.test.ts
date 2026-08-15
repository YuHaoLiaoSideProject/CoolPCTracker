// web/src/views/__tests__/ProductDetailView.test.ts — 四態狀態機＋目標價互動（BDD E3/E4/E5/E6/E7/E8/E13）
// mock useItems（003 契約）與 PriceTrendChart（jsdom 無 canvas）；用 memory router 直接進 /product/:id。
import { describe, expect, it, vi, beforeEach } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import { createRouter, createMemoryHistory } from "vue-router"
import type { Item } from "@/types/item"

vi.mock("@/composables/useItems", async () => {
  const { ref } = await import("vue")
  // factory 閉包內建立一次 → 每次 useItems() 回傳同一組 ref（單例共享語義）
  const items = ref<Item[]>([])
  const meta = ref<{ crawled_at: string } | null>(null)
  const loading = ref(true)
  const error = ref<"fetch" | "parse" | null>(null)
  const retry = vi.fn()
  const isStale = ref(false)
  return {
    useItems: () => ({ items, meta, loading, error, retry, isStale }),
  }
})

vi.mock("@/components/PriceTrendChart.vue", () => ({
  default: {
    name: "PriceTrendChartStub",
    props: ["history", "targetPrice", "yMin", "yMax"],
    template: '<div class="chart-stub" />',
  },
}))

import { useItems } from "@/composables/useItems"
import ProductDetailView from "@/views/ProductDetailView.vue"

// mock 的 useItems 每次回傳同一組 ref（同 factory 閉包 → 單例共享語義）
const state = (): ReturnType<typeof useItems> => useItems()

const base: Omit<Item, "id" | "name"> = {
  category: "CPU",
  spec: { brand: "Intel", cores: 14, socket: "LGA1700" },
  status: "in_stock",
  first_seen: "2026-08-13",
  last_seen: "2026-08-15",
  history: [],
}
const i5 = (): Item => ({
  ...base,
  id: "3f9a1c2b8e4d5f6a",
  name: "Intel i5-13600K",
  history: [
    { d: "2026-08-13", p: 11500 },
    { d: "2026-08-14", p: 10500 },
    { d: "2026-08-15", p: 9990 },
  ],
})

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

  it("圖表收到 history／targetPrice／yMin／yMax props；WatchActions 收到 itemId", async () => {
    state().items.value = [i5()]
    const { w } = await mountView("3f9a1c2b8e4d5f6a")
    const chart = chartStub(w)
    expect(chart.props("history")).toHaveLength(3)
    expect(chart.props("targetPrice")).toBeNull()
    expect(chart.props("yMin")).toBeCloseTo(9990 * 0.98)
    expect(chart.props("yMax")).toBeCloseTo(11500 * 1.02)
    expect(w.findComponent({ name: "WatchActions" }).props("itemId")).toBe("3f9a1c2b8e4d5f6a")
  })

  it("history 空（E4）→ 目前價「—」＋尚無歷史資料＋不渲染圖表", async () => {
    state().items.value = [{ ...base, id: "empty-1", name: "新品 X", history: [] }]
    const { w } = await mountView("empty-1")
    expect(w.text()).toContain("尚無歷史資料")
    expect(w.find(".price-current").text()).toBe("—")
    expect(chartStub(w).exists()).toBe(false)
  })

  it("僅一筆（E5）→ 首日追蹤，尚無漲跌比較；low=目前價", async () => {
    state().items.value = [{ ...base, id: "single-1", name: "新品 X", history: [{ d: "2026-08-15", p: 5990 }] }]
    const { w } = await mountView("single-1")
    expect(w.text()).toContain("首日追蹤，尚無漲跌比較")
    expect(w.find(".price-low").text()).toContain("NT$ 5,990")
    expect(w.find(".low-date").text()).toContain("2026-08-15")
    expect(chartStub(w).exists()).toBe(true)
  })

  it("下架商品（E13）→ 此商品已下架 badge 且價格照常顯示", async () => {
    state().items.value = [{ ...base, id: "gone-1", name: "停產 Z", status: "gone", history: [{ d: "2026-08-14", p: 4490 }] }]
    const { w } = await mountView("gone-1")
    expect(w.find(".badge-gone").text()).toBe("此商品已下架")
    expect(w.find(".price-current").text()).toBe("NT$ 4,490")
  })
})

describe("目標價互動（E6/E7/E12）", () => {
  async function setup() {
    state().items.value = [i5()] // 歷史區間 9990~11500
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
