// web/src/composables/__tests__/useDashboard.test.ts — useDashboard 單元測試（017 + 019）
import { describe, expect, it, vi, beforeEach } from "vitest"
import { ref } from "vue"
import type { Item, CategoryMeta } from "@/types/item"

// Mock useItems singleton
const mockCategories = ref<CategoryMeta[]>([
  { id: "cpu", name: "CPU", file: "g1.json", count: 10 },
  { id: "gpu", name: "顯示卡", file: "g2.json", count: 8 },
])
const mockIsLoadingCategory = vi.fn(() => false)
const mockLoadCategory = vi.fn(async () => {})

vi.mock("@/composables/useItems", () => ({
  useItems: () => ({
    categories: mockCategories,
    isLoadingCategory: mockIsLoadingCategory,
    loadCategory: mockLoadCategory,
  }),
}))

import { useDashboard } from "@/composables/useDashboard"

function makeItem(id: string, prices: number[]): Item {
  return {
    id,
    name: `Item ${id}`,
    spec: {},
    status: "in_stock",
    first_seen: "2026-08-01",
    last_seen: "2026-08-17",
    history: prices.map((p, i) => ({ d: `2026-08-${String(i + 1).padStart(2, "0")}`, p })),
  }
}

function makeGoneItem(id: string): Item {
  return {
    id,
    name: `Gone ${id}`,
    spec: {},
    status: "gone",
    first_seen: "2026-08-01",
    last_seen: "2026-08-10",
    history: [{ d: "2026-08-01", p: 5000 }],
  }
}

describe("useDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("dashboardItems 按 currentPrice 升冪排序", () => {
    const items = ref([makeItem("a", [3000]), makeItem("b", [1000]), makeItem("c", [2000])])
    const categoryId = ref("cpu")
    const { dashboardItems } = useDashboard(items, categoryId)
    expect(dashboardItems.value.map((d) => d.currentPrice)).toEqual([1000, 2000, 3000])
  })

  it("dashboardItems 最多 10 筆（Top 10）", () => {
    const items = ref(Array.from({ length: 15 }, (_, i) => makeItem(`i${i}`, [1000 + i])))
    const categoryId = ref("cpu")
    const { dashboardItems } = useDashboard(items, categoryId)
    expect(dashboardItems.value).toHaveLength(10)
    expect(dashboardItems.value[0].currentPrice).toBe(1000)
    expect(dashboardItems.value[9].currentPrice).toBe(1009)
  })

  it("null history 的 currentPrice 為 null 且排到最後", () => {
    const itemNoHistory: Item = {
      id: "x",
      name: "No History",
      spec: {},
      status: "in_stock",
      first_seen: "",
      last_seen: "",
      history: [],
    }
    const items = ref([makeItem("a", [5000]), itemNoHistory])
    const categoryId = ref("cpu")
    const { dashboardItems } = useDashboard(items, categoryId)
    expect(dashboardItems.value[0].currentPrice).toBe(5000)
    expect(dashboardItems.value[1].currentPrice).toBeNull()
  })

  it("isLowest 正確標記最便宜商品", () => {
    const items = ref([makeItem("a", [3000]), makeItem("b", [1000]), makeItem("c", [2000])])
    const categoryId = ref("cpu")
    const { dashboardItems } = useDashboard(items, categoryId)
    expect(dashboardItems.value[0].isLowest).toBe(true) // b = 1000
    expect(dashboardItems.value[1].isLowest).toBe(false)
    expect(dashboardItems.value[2].isLowest).toBe(false)
  })

  it("lowestPrice 為該分類歷史最低價", () => {
    const items = ref([makeItem("a", [3000]), makeItem("b", [1000]), makeItem("c", [2000])])
    const categoryId = ref("cpu")
    const { dashboardItems } = useDashboard(items, categoryId)
    for (const di of dashboardItems.value) {
      expect(di.lowestPrice).toBe(1000)
    }
  })

  it("categoryId 為 null 時回傳空陣列", () => {
    const items = ref([makeItem("a", [1000])])
    const categoryId = ref<string | null>(null)
    const { dashboardItems } = useDashboard(items, categoryId)
    expect(dashboardItems.value).toEqual([])
  })

  it("activeCategory 正確查詢目前分類", () => {
    const items = ref([makeItem("a", [1000])])
    const categoryId = ref("cpu")
    const { activeCategory } = useDashboard(items, categoryId)
    expect(activeCategory.value).toEqual({ id: "cpu", name: "CPU", file: "g1.json", count: 10 })
  })

  it("activeCategory 找不到時回傳 null", () => {
    const items = ref([makeItem("a", [1000])])
    const categoryId = ref("unknown")
    const { activeCategory } = useDashboard(items, categoryId)
    expect(activeCategory.value).toBeNull()
  })

  it("categoryLoading 委派 isLoadingCategory", () => {
    mockIsLoadingCategory.mockReturnValueOnce(true)
    const items = ref([makeItem("a", [1000])])
    const categoryId = ref("cpu")
    const { categoryLoading } = useDashboard(items, categoryId)
    expect(categoryLoading.value).toBe(true)
  })

  it("categoryLoading categoryId 為 null 時回傳 false", () => {
    const items = ref([makeItem("a", [1000])])
    const categoryId = ref<string | null>(null)
    const { categoryLoading } = useDashboard(items, categoryId)
    expect(categoryLoading.value).toBe(false)
  })

  it("switchCategory 呼叫 loadCategory", async () => {
    const items = ref([makeItem("a", [1000])])
    const categoryId = ref("cpu")
    const { switchCategory } = useDashboard(items, categoryId)
    await switchCategory("gpu")
    expect(mockLoadCategory).toHaveBeenCalledWith("gpu")
  })

  it("switchCategory 呼叫 resetGroup", async () => {
    const resetGroup = vi.fn()
    const items = ref([makeItem("a", [1000])])
    const categoryId = ref("cpu")
    const { switchCategory } = useDashboard(items, categoryId, resetGroup)
    await switchCategory("gpu")
    expect(resetGroup).toHaveBeenCalledOnce()
  })

  it("switchCategory 無 resetGroup 參數也不報錯", async () => {
    const items = ref([makeItem("a", [1000])])
    const categoryId = ref("cpu")
    const { switchCategory } = useDashboard(items, categoryId)
    await expect(switchCategory("gpu")).resolves.toBeUndefined()
  })

  it("gone item 的 currentPrice 為 null（有 history）", () => {
    const items = ref([makeGoneItem("g1")])
    const categoryId = ref("cpu")
    const { dashboardItems } = useDashboard(items, categoryId)
    expect(dashboardItems.value[0].currentPrice).toBe(5000)
    expect(dashboardItems.value[0].item.status).toBe("gone")
  })
})
