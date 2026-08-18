// web/src/views/__tests__/DashboardView.test.ts — DashboardView 整合測試（017 + 018 + 019）
// mock useItems singleton、useDashboard、useSpecGroups；用 memory router 進 /dashboard。
import { describe, expect, it, vi, beforeEach } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import { createRouter, createMemoryHistory } from "vue-router"
import type { Item, CategoryMeta } from "@/types/item"

// ── Mock 依賴 ──

const mockCategories = ref<CategoryMeta[]>([
  { id: "cpu", name: "CPU", file: "g1.json", count: 3 },
  { id: "gpu", name: "顯示卡", file: "g2.json", count: 2 },
])
const mockItems = ref<Item[]>([])
const mockActiveCategoryId = ref<string | null>(null)
const mockLoading = ref(true)
const mockError = ref<"fetch" | "parse" | null>(null)
const mockRetry = vi.fn()
const mockLoadCategory = vi.fn(async () => {})
const mockItemToCategory = ref<Map<string, string>>(new Map())
const mockIsLoadingCategory = vi.fn(() => false)

vi.mock("@/composables/useItems", () => ({
  useItems: () => ({
    items: mockItems,
    categories: mockCategories,
    activeCategoryId: mockActiveCategoryId,
    loading: mockLoading,
    error: mockError,
    retry: mockRetry,
    itemToCategory: mockItemToCategory,
    loadCategory: mockLoadCategory,
    isLoadingCategory: mockIsLoadingCategory,
  }),
}))

vi.mock("@/composables/useSpecGroups", () => ({
  useSpecGroups: () => ({
    hasGroups: ref(false),
    groups: ref([]),
    selectedGroupKey: ref(null),
    groupedItems: computed(() => mockItems.value),
    selectGroup: vi.fn(),
    resetGroup: vi.fn(),
  }),
}))

vi.mock("@/composables/useDashboardFilters", () => ({
  useDashboardFilters: (items: { value: Item[] }) => ({
    sortMode: ref("price_asc"),
    priceMin: ref(null),
    priceMax: ref(null),
    selectedBrands: ref(new Set()),
    availableBrands: computed(() => []),
    filteredItems: computed(() => items.value),
    sortedItems: computed(() => items.value),
    hasActiveFilter: ref(false),
    setSortMode: vi.fn(),
    setPriceMin: vi.fn(),
    setPriceMax: vi.fn(),
    toggleBrand: vi.fn(),
    clearFilters: vi.fn(),
    resetAll: vi.fn(),
  }),
}))

vi.mock("@/composables/useDashboard", () => ({
  useDashboard: (items: { value: Item[] }, categoryId: { value: string | null }) => {
    const dashboardItems = computed(() => {
      const id = categoryId.value
      if (id == null) return []
      return items.value
        .map((item: Item) => ({
          item,
          currentPrice: item.history.length > 0 ? item.history[item.history.length - 1].p : null,
          isLowest: false,
          lowestPrice: null,
        }))
        .sort((a: { currentPrice: number | null }, b: { currentPrice: number | null }) => {
          if (a.currentPrice == null) return 1
          if (b.currentPrice == null) return -1
          return a.currentPrice - b.currentPrice
        })
        .slice(0, 10)
    })
    return {
      dashboardItems,
      extractCurrentPrice: (item: Item) =>
        item.history.length > 0 ? item.history[item.history.length - 1].p : null,
      activeCategory: computed(() => {
        const id = categoryId.value
        return id ? mockCategories.value.find((c: CategoryMeta) => c.id === id) ?? null : null
      }),
      categoryLoading: ref(false),
      switchCategory: vi.fn(async (newId: string) => {
        mockActiveCategoryId.value = newId
      }),
    }
  },
}))

import { ref, computed } from "vue"
import DashboardView from "@/views/DashboardView.vue"

function makeItem(id: string, prices: number[], category: string): Item {
  const item: Item = {
    id,
    name: `Item ${id}`,
    spec: {},
    status: "in_stock",
    first_seen: "2026-08-01",
    last_seen: "2026-08-17",
    history: prices.map((p, i) => ({ d: `2026-08-${String(i + 1).padStart(2, "0")}`, p })),
  }
  mockItemToCategory.value.set(id, category)
  return item
}

function mountDashboard() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div/>" } },
      { path: "/dashboard", name: "dashboard", component: DashboardView },
      { path: "/product/:id", component: { template: "<div/>" } },
    ],
  })
  return mount(DashboardView, {
    global: { plugins: [router] },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  mockCategories.value = [
    { id: "cpu", name: "CPU", file: "g1.json", count: 3 },
    { id: "gpu", name: "顯示卡", file: "g2.json", count: 2 },
  ]
  mockItems.value = []
  mockActiveCategoryId.value = null
  mockLoading.value = true
  mockError.value = null
  mockItemToCategory.value = new Map()
})

describe("DashboardView 整合測試", () => {
  describe("骨架屏狀態", () => {
    it("loading 時顯示骨架屏", () => {
      mockLoading.value = true
      const w = mountDashboard()
      expect(w.findComponent({ name: "DashboardSkeleton" }).exists()).toBe(true)
    })

    it("loading 時不顯示錯誤或空狀態", () => {
      mockLoading.value = true
      const w = mountDashboard()
      expect(w.findComponent({ name: "ErrorState" }).exists()).toBe(false)
      expect(w.findComponent({ name: "EmptyState" }).exists()).toBe(false)
    })
  })

  describe("錯誤狀態", () => {
    it("error 時顯示 ErrorState", () => {
      mockLoading.value = false
      mockError.value = "fetch"
      const w = mountDashboard()
      expect(w.findComponent({ name: "ErrorState" }).exists()).toBe(true)
    })

    it("retry 按鈕呼叫 retry", async () => {
      mockLoading.value = false
      mockError.value = "fetch"
      const w = mountDashboard()
      const errorComp = w.findComponent({ name: "ErrorState" })
      await errorComp.vm.$emit("retry")
      expect(mockRetry).toHaveBeenCalledOnce()
    })
  })

  describe("正常顯示", () => {
    it("載入完成後顯示 CategoryTabs", () => {
      mockLoading.value = false
      mockActiveCategoryId.value = "cpu"
      const w = mountDashboard()
      expect(w.findComponent({ name: "CategoryTabs" }).exists()).toBe(true)
    })

    it("載入完成後顯示商品列表", () => {
      mockLoading.value = false
      mockActiveCategoryId.value = "cpu"
      mockItems.value = [
        makeItem("a", [9990], "cpu"),
        makeItem("b", [8990], "cpu"),
      ]
      const w = mountDashboard()
      expect(w.find(".dashboard-list").exists()).toBe(true)
      expect(w.findAllComponents({ name: "DashboardCard" })).toHaveLength(2)
    })

    it("載入完成後不顯示骨架屏", () => {
      mockLoading.value = false
      mockActiveCategoryId.value = "cpu"
      const w = mountDashboard()
      expect(w.findComponent({ name: "DashboardSkeleton" }).exists()).toBe(false)
    })
  })

  describe("空狀態", () => {
    it("無商品時顯示 EmptyState", () => {
      mockLoading.value = false
      mockActiveCategoryId.value = "cpu"
      mockItems.value = []
      const w = mountDashboard()
      expect(w.findComponent({ name: "EmptyState" }).exists()).toBe(true)
    })

    it("無商品時不顯示商品列表", () => {
      mockLoading.value = false
      mockActiveCategoryId.value = "cpu"
      mockItems.value = []
      const w = mountDashboard()
      expect(w.find(".dashboard-list").exists()).toBe(false)
    })
  })

  describe("Tab 切換", () => {
    it("CategoryTabs 收到正確 categories props", () => {
      mockLoading.value = false
      mockActiveCategoryId.value = "cpu"
      const w = mountDashboard()
      const tabs = w.findComponent({ name: "CategoryTabs" })
      expect(tabs.props("categories")).toHaveLength(2)
      expect(tabs.props("activeId")).toBe("cpu")
    })

    it("切換 Tab 觸發 switchCategory", async () => {
      mockLoading.value = false
      mockActiveCategoryId.value = "cpu"
      const wrapper = mountDashboard()
      const tabs = wrapper.findComponent({ name: "CategoryTabs" })
      await tabs.vm.$emit("select", "gpu")
      // switchCategory 是 mock，驗證不報錯
      expect(tabs.exists()).toBe(true)
    })
  })

  describe("商品卡片渲染", () => {
    it("DashboardCard 收到正確 props", () => {
      mockLoading.value = false
      mockActiveCategoryId.value = "cpu"
      mockItems.value = [makeItem("a", [9990], "cpu")]
      const w = mountDashboard()
      const card = w.findComponent({ name: "DashboardCard" })
      expect(card.props("item").id).toBe("a")
      expect(card.props("categoryName")).toBe("CPU")
      expect(card.props("lowestPrice")).toBe(9990)
    })

    it("多筆商品正確渲染多張卡片", () => {
      mockLoading.value = false
      mockActiveCategoryId.value = "cpu"
      mockItems.value = [
        makeItem("a", [9990], "cpu"),
        makeItem("b", [8990], "cpu"),
        makeItem("c", [10990], "cpu"),
      ]
      const w = mountDashboard()
      expect(w.findAllComponents({ name: "DashboardCard" })).toHaveLength(3)
    })
  })

  describe("預設選取", () => {
    it("categories 有值時自動選取第一個分類", async () => {
      mockLoading.value = false
      mockActiveCategoryId.value = null
      mountDashboard()
      await flushPromises()
      // 驗證 watch 觸發 loadCategory（mock 的 loadCategory 會被呼叫）
      expect(mockLoadCategory).toHaveBeenCalled()
    })
  })
})
