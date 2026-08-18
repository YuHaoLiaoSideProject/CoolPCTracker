// web/src/composables/__tests__/useDashboardFilters.test.ts — useDashboardFilters 單元測試（022）
import { describe, expect, it, beforeEach } from "vitest"
import { ref, nextTick, type Ref } from "vue"
import type { Item } from "@/types/item"
import { useDashboardFilters } from "@/composables/useDashboardFilters"

// ── Helpers ──

function makeItem(
  id: string,
  price: number | null,
  brand?: string,
  lastSeen?: string,
): Item {
  const history =
    price != null
      ? [{ d: "2026-08-17", p: price }]
      : []
  return {
    id,
    name: `Item ${id}`,
    spec: brand ? { brand } : {},
    status: "in_stock",
    first_seen: "2026-08-01",
    last_seen: lastSeen ?? "2026-08-17",
    history,
  }
}

function makeItems(): Item[] {
  return [
    makeItem("a", 3000, "金士頓", "2026-08-17"),
    makeItem("b", 1500, "美光", "2026-08-16"),
    makeItem("c", 8000, "金士頓", "2026-08-15"),
    makeItem("d", 500, "三星", "2026-08-14"),
    makeItem("e", null, "美光", "2026-08-13"),
  ]
}

// ── Tests ──

describe("useDashboardFilters", () => {
  let items: Ref<Item[]>

  beforeEach(() => {
    items = ref(makeItems())
  })

  describe("sortMode", () => {
    it("預設 sortMode 為 price_asc", () => {
      const { sortMode } = useDashboardFilters(items)
      expect(sortMode.value).toBe("price_asc")
    })

    it("setSortMode 切換排序", () => {
      const { sortMode, setSortMode } = useDashboardFilters(items)
      setSortMode("price_desc")
      expect(sortMode.value).toBe("price_desc")
      setSortMode("recently_updated")
      expect(sortMode.value).toBe("recently_updated")
    })
  })

  describe("價格篩選", () => {
    it("priceMin 篩選價格下限", () => {
      const { sortedItems, setPriceMin } = useDashboardFilters(items)
      setPriceMin(1500)
      const ids = sortedItems.value.map((i) => i.id)
      expect(ids).toContain("a")  // 3000
      expect(ids).toContain("b")  // 1500
      expect(ids).toContain("c")  // 8000
      expect(ids).not.toContain("d") // 500
    })

    it("priceMax 篩選價格上限", () => {
      const { sortedItems, setPriceMax } = useDashboardFilters(items)
      setPriceMax(3000)
      const ids = sortedItems.value.map((i) => i.id)
      expect(ids).toContain("a")  // 3000
      expect(ids).toContain("b")  // 1500
      expect(ids).toContain("d")  // 500
      expect(ids).not.toContain("c") // 8000
    })

    it("priceMin + priceMax 價格區間篩選", () => {
      const { sortedItems, setPriceMin, setPriceMax } = useDashboardFilters(items)
      setPriceMin(1500)
      setPriceMax(5000)
      const ids = sortedItems.value.map((i) => i.id)
      expect(ids).toContain("a")  // 3000
      expect(ids).toContain("b")  // 1500
      expect(ids).not.toContain("c") // 8000
      expect(ids).not.toContain("d") // 500
    })

    it("null price 商品被 priceMin 排除", () => {
      const { sortedItems, setPriceMin } = useDashboardFilters(items)
      setPriceMin(100)
      const ids = sortedItems.value.map((i) => i.id)
      expect(ids).not.toContain("e") // null price
    })

    it("null price 商品被 priceMax 排除", () => {
      const { sortedItems, setPriceMax } = useDashboardFilters(items)
      setPriceMax(99999)
      const ids = sortedItems.value.map((i) => i.id)
      expect(ids).not.toContain("e") // null price
    })
  })

  describe("auto-swap min > max", () => {
    it("priceMin > priceMax 時自動交換", async () => {
      const { priceMin, priceMax, setPriceMin, setPriceMax } = useDashboardFilters(items)
      setPriceMax(5000)
      setPriceMin(15000)
      await nextTick()
      expect(priceMin.value).toBe(5000)
      expect(priceMax.value).toBe(15000)
    })
  })

  describe("品牌篩選", () => {
    it("toggleBrand 勾選單一品牌", () => {
      const { sortedItems, toggleBrand } = useDashboardFilters(items)
      toggleBrand("金士頓")
      const ids = sortedItems.value.map((i) => i.id)
      expect(ids).toContain("a") // 金士頓
      expect(ids).toContain("c") // 金士頓
      expect(ids).not.toContain("b") // 美光
      expect(ids).not.toContain("d") // 三星
    })

    it("多品牌篩選取聯集", () => {
      const { sortedItems, toggleBrand } = useDashboardFilters(items)
      toggleBrand("金士頓")
      toggleBrand("美光")
      const ids = sortedItems.value.map((i) => i.id)
      expect(ids).toContain("a") // 金士頓
      expect(ids).toContain("b") // 美光
      expect(ids).toContain("c") // 金士頓
      expect(ids).not.toContain("d") // 三星
    })

    it("取消品牌篩選恢復全部", () => {
      const { sortedItems, toggleBrand } = useDashboardFilters(items)
      toggleBrand("金士頓")
      toggleBrand("金士頓") // 取消
      const ids = sortedItems.value.map((i) => i.id)
      expect(ids).toContain("a")
      expect(ids).toContain("b")
      expect(ids).toContain("c")
      expect(ids).toContain("d")
    })
  })

  describe("hasActiveFilter", () => {
    it("無篩選時 hasActiveFilter 為 false", () => {
      const { hasActiveFilter } = useDashboardFilters(items)
      expect(hasActiveFilter.value).toBe(false)
    })

    it("設定 priceMin 後 hasActiveFilter 為 true", () => {
      const { hasActiveFilter, setPriceMin } = useDashboardFilters(items)
      setPriceMin(1000)
      expect(hasActiveFilter.value).toBe(true)
    })

    it("設定 priceMax 後 hasActiveFilter 為 true", () => {
      const { hasActiveFilter, setPriceMax } = useDashboardFilters(items)
      setPriceMax(5000)
      expect(hasActiveFilter.value).toBe(true)
    })

    it("勾選品牌後 hasActiveFilter 為 true", () => {
      const { hasActiveFilter, toggleBrand } = useDashboardFilters(items)
      toggleBrand("金士頓")
      expect(hasActiveFilter.value).toBe(true)
    })
  })

  describe("clearFilters", () => {
    it("清除篩選（保留 sortMode）", () => {
      const { sortMode, hasActiveFilter, setSortMode, setPriceMin, toggleBrand, clearFilters } =
        useDashboardFilters(items)
      setSortMode("price_desc")
      setPriceMin(1000)
      toggleBrand("金士頓")
      clearFilters()
      expect(sortMode.value).toBe("price_desc") // 保留
      expect(hasActiveFilter.value).toBe(false)
    })
  })

  describe("resetAll", () => {
    it("重設全部（含 sortMode）", () => {
      const { sortMode, hasActiveFilter, setSortMode, setPriceMin, toggleBrand, resetAll } =
        useDashboardFilters(items)
      setSortMode("price_desc")
      setPriceMin(1000)
      toggleBrand("金士頓")
      resetAll()
      expect(sortMode.value).toBe("price_asc")
      expect(hasActiveFilter.value).toBe(false)
    })
  })

  describe("availableBrands", () => {
    it("從商品中提取唯一品牌並排序", () => {
      const { availableBrands } = useDashboardFilters(items)
      expect(availableBrands.value).toEqual(["三星", "金士頓", "美光"])
    })

    it("無品牌欄位時回傳空陣列", () => {
      const noBrandItems = ref([
        makeItem("x", 1000),
        makeItem("y", 2000),
      ])
      const { availableBrands } = useDashboardFilters(noBrandItems)
      expect(availableBrands.value).toEqual([])
    })
  })

  describe("sortedItems 排序", () => {
    it("price_asc 由低到高排序", () => {
      const { sortedItems, setSortMode } = useDashboardFilters(items)
      setSortMode("price_asc")
      const prices = sortedItems.value
        .map((i) => (i.history.length > 0 ? i.history[i.history.length - 1].p : null))
        .filter((p) => p != null)
      expect(prices).toEqual([500, 1500, 3000, 8000])
    })

    it("price_desc 由高到低排序", () => {
      const { sortedItems, setSortMode } = useDashboardFilters(items)
      setSortMode("price_desc")
      const prices = sortedItems.value
        .map((i) => (i.history.length > 0 ? i.history[i.history.length - 1].p : null))
        .filter((p) => p != null)
      expect(prices).toEqual([8000, 3000, 1500, 500])
    })

    it("recently_updated 依 last_seen 由新到舊", () => {
      const { sortedItems, setSortMode } = useDashboardFilters(items)
      setSortMode("recently_updated")
      const lastSeens = sortedItems.value.map((i) => i.last_seen)
      expect(lastSeens).toEqual([
        "2026-08-17",
        "2026-08-16",
        "2026-08-15",
        "2026-08-14",
        "2026-08-13",
      ])
    })

    it("null price 排序時置底（price_asc）", () => {
      const { sortedItems, setSortMode } = useDashboardFilters(items)
      setSortMode("price_asc")
      const lastItem = sortedItems.value[sortedItems.value.length - 1]
      expect(lastItem.id).toBe("e") // null price
    })

    it("null price 排序時置底（price_desc）", () => {
      const { sortedItems, setSortMode } = useDashboardFilters(items)
      setSortMode("price_desc")
      const lastItem = sortedItems.value[sortedItems.value.length - 1]
      expect(lastItem.id).toBe("e") // null price
    })
  })

  describe("篩選交集", () => {
    it("價格篩選 + 品牌篩選交集", () => {
      const { sortedItems, setPriceMin, toggleBrand } = useDashboardFilters(items)
      setPriceMin(2000)
      toggleBrand("金士頓")
      const ids = sortedItems.value.map((i) => i.id)
      expect(ids).toContain("a")  // 3000, 金士頓
      expect(ids).toContain("c")  // 8000, 金士頓
      expect(ids).not.toContain("b") // 1500, 美光
      expect(ids).not.toContain("d") // 500, 三星
    })
  })
})
