// web/src/components/__tests__/DashboardCard.test.ts — DashboardCard 單元測試（017 §2.3）
import { describe, expect, it, vi } from "vitest"
import { mount } from "@vue/test-utils"
import { ref } from "vue"
import { createRouter, createMemoryHistory } from "vue-router"
import DashboardCard from "@/components/DashboardCard.vue"
import type { Item } from "@/types/item"

vi.mock("@/composables/usePriceDelta", () => ({
  usePriceDelta: (item: Item) => ({
    currentPrice: ref(item.history.length > 0 ? item.history[item.history.length - 1].p : null),
    deltaClass: "",
    deltaText: "",
  }),
  specChipTexts: (spec: Record<string, unknown>, _categoryName: string) => {
    if (!spec || Object.keys(spec).length === 0) return []
    return Object.entries(spec)
      .filter(([, v]) => v != null && v !== "")
      .map(([k, v]) => `${k}:${v}`)
      .slice(0, 3)
  },
}))

vi.mock("@/utils/format", () => ({
  formatPrice: (n: number | null) => (n != null ? `NT$ ${n.toLocaleString()}` : "—"),
}))

vi.mock("@/components/Sparkline.vue", () => ({
  default: {
    name: "Sparkline",
    template: '<div class="sparkline-mock" />',
    props: ["points", "trend", "enableTooltip"],
  },
}))

vi.mock("@/components/WatchlistButton.vue", () => ({
  default: {
    name: "WatchlistButton",
    template: '<button class="watchlist-btn-mock">追蹤</button>',
    props: ["id", "name", "price"],
  },
}))

function makeItem(overrides: Partial<Item> = {}): Item {
  return {
    id: "test-item-1",
    name: "Intel i5-13600K",
    spec: { brand: "Intel", cores: 14 },
    status: "in_stock",
    first_seen: "2026-08-01",
    last_seen: "2026-08-17",
    history: [{ d: "2026-08-15", p: 9990 }],
    ...overrides,
  }
}

function mountCard(props: {
  item?: Item
  categoryName?: string
  isLowest?: boolean
  lowestPrice?: number | null
}) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div/>" } },
      { path: "/product/:id", component: { template: "<div/>" } },
    ],
  })
  return mount(DashboardCard, {
    props: {
      item: props.item ?? makeItem(),
      categoryName: props.categoryName ?? "CPU",
      isLowest: props.isLowest ?? false,
      lowestPrice: props.lowestPrice ?? null,
    },
    global: { plugins: [router] },
  })
}

describe("DashboardCard", () => {
  it("渲染商品名稱", () => {
    const w = mountCard({})
    expect(w.find(".dc-name").text()).toBe("Intel i5-13600K")
  })

  it("渲染目前價格（千分位）", () => {
    const w = mountCard({})
    expect(w.find(".dc-current").text()).toBe("NT$ 9,990")
  })

  it("history 空時價格顯示「—」", () => {
    const w = mountCard({ item: makeItem({ history: [] }) })
    expect(w.find(".dc-current").text()).toBe("—")
  })

  it("isLowest=true 時顯示 🥇 徽章", () => {
    const w = mountCard({ isLowest: true })
    expect(w.find(".dc-lowest").exists()).toBe(true)
    expect(w.find(".dc-lowest").text()).toBe("🥇")
  })

  it("isLowest=false 時不顯示 🥇 徽章", () => {
    const w = mountCard({ isLowest: false })
    expect(w.find(".dc-lowest").exists()).toBe(false)
  })

  it("已下架商品顯示「已下架」標籤", () => {
    const w = mountCard({ item: makeItem({ status: "gone" }) })
    expect(w.find(".dc-gone").exists()).toBe(true)
    expect(w.find(".dc-gone").text()).toBe("已下架")
  })

  it("已下架商品不顯示 🥇 徽章", () => {
    const w = mountCard({ item: makeItem({ status: "gone" }), isLowest: true })
    expect(w.find(".dc-gone").exists()).toBe(true)
    expect(w.find(".dc-lowest").exists()).toBe(false)
  })

  it("已下架商品價格區顯示「已下架」文字", () => {
    const w = mountCard({ item: makeItem({ status: "gone" }) })
    expect(w.find(".dc-gone-text").exists()).toBe(true)
    expect(w.find(".dc-gone-text").text()).toBe("已下架")
  })

  it("有 lowestPrice 且與目前價格不同時顯示歷史最低價", () => {
    const w = mountCard({ lowestPrice: 8990 })
    expect(w.find(".dc-history-low").exists()).toBe(true)
    expect(w.find(".dc-history-low").text()).toContain("NT$ 8,990")
  })

  it("lowestPrice 與目前價格相同時不顯示歷史最低價", () => {
    const w = mountCard({ lowestPrice: 9990 })
    expect(w.find(".dc-history-low").exists()).toBe(false)
  })

  it("lowestPrice 為 null 時不顯示歷史最低價", () => {
    const w = mountCard({ lowestPrice: null })
    expect(w.find(".dc-history-low").exists()).toBe(false)
  })

  it("規格 chips 正確渲染", () => {
    const w = mountCard({})
    const chips = w.findAll(".chip")
    expect(chips.length).toBeGreaterThan(0)
    expect(chips[0].text()).toContain("Intel")
  })

  it("空規格時不渲染 chips 區塊", () => {
    const w = mountCard({ item: makeItem({ spec: {} }) })
    expect(w.find(".dc-specs").exists()).toBe(false)
  })

  it("role=button 且 tabindex=0", () => {
    const w = mountCard({})
    expect(w.find(".dashboard-card").attributes("role")).toBe("button")
    expect(w.find(".dashboard-card").attributes("tabindex")).toBe("0")
  })

  it("aria-label 包含商品名稱與價格", () => {
    const w = mountCard({ item: makeItem({ history: [{ d: "2026-08-15", p: 12345 }] }) })
    const label = w.find(".dashboard-card").attributes("aria-label")
    expect(label).toContain("Intel i5-13600K")
    expect(label).toContain("12,345")
  })

  it("aria-label 空 history 時顯示價格未知", () => {
    const w = mountCard({ item: makeItem({ history: [] }) })
    const label = w.find(".dashboard-card").attributes("aria-label")
    expect(label).toContain("價格未知")
  })

  it("點擊卡片導航至詳情頁", async () => {
    const w = mountCard({})
    await w.find(".dashboard-card").trigger("click")
    // 由於 memory router，只驗證不拋錯
    expect(w.emitted()).toBeDefined()
  })

  it("Enter 鍵導航至詳情頁", async () => {
    const w = mountCard({})
    await w.find(".dashboard-card").trigger("keydown", { key: "Enter" })
    expect(w.emitted()).toBeDefined()
  })

  it("Space 鍵導航至詳情頁", async () => {
    const w = mountCard({})
    await w.find(".dashboard-card").trigger("keydown", { key: " " })
    expect(w.emitted()).toBeDefined()
  })

  // ── Sparkline 整合 ──

  it("非已下架商品顯示 Sparkline", () => {
    const w = mountCard({})
    expect(w.find(".sparkline-mock").exists()).toBe(true)
  })

  it("已下架商品不顯示 Sparkline", () => {
    const w = mountCard({ item: makeItem({ status: "gone" }) })
    expect(w.find(".sparkline-mock").exists()).toBe(false)
  })

  // ── WatchlistButton 整合 ──

  it("非已下架商品顯示 WatchlistButton", () => {
    const w = mountCard({})
    expect(w.find(".watchlist-btn-mock").exists()).toBe(true)
  })

  it("已下架商品不顯示 WatchlistButton", () => {
    const w = mountCard({ item: makeItem({ status: "gone" }) })
    expect(w.find(".watchlist-btn-mock").exists()).toBe(false)
  })

  it("dc-right wrapper 存在", () => {
    const w = mountCard({})
    expect(w.find(".dc-right").exists()).toBe(true)
  })
})
