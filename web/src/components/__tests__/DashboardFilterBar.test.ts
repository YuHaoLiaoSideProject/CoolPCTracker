// web/src/components/__tests__/DashboardFilterBar.test.ts — DashboardFilterBar 單元測試（022）
import { describe, expect, it } from "vitest"
import { mount } from "@vue/test-utils"
import DashboardFilterBar from "@/components/DashboardFilterBar.vue"
import type { SortMode } from "@/types/dashboardFilter"

// ── Helpers ──

function makeProps(overrides?: Partial<InstanceType<typeof DashboardFilterBar>["$props"]>) {
  return {
    sortMode: "price_asc" as SortMode,
    priceMin: null,
    priceMax: null,
    availableBrands: [] as string[],
    selectedBrands: new Set<string>(),
    resultCount: 10,
    totalCount: 10,
    hasActiveFilter: false,
    ...overrides,
  }
}

function mountBar(propsOverrides?: Partial<InstanceType<typeof DashboardFilterBar>["$props"]>) {
  return mount(DashboardFilterBar, { props: makeProps(propsOverrides) })
}

// ── Tests ──

describe("DashboardFilterBar", () => {
  describe("排序下拉", () => {
    it("渲染排序下拉（3 options）", () => {
      const w = mountBar()
      const select = w.find("select.sort-select")
      expect(select.exists()).toBe(true)
      const options = select.findAll("option")
      expect(options).toHaveLength(3)
    })

    it("切換排序 emit update:sort", async () => {
      const w = mountBar()
      const select = w.find("select.sort-select")
      await select.setValue("price_desc")
      expect(w.emitted("update:sort")).toBeTruthy()
      expect(w.emitted("update:sort")![0]).toEqual(["price_desc"])
    })
  })

  describe("價格輸入框", () => {
    it("渲染 2 個 input[type=number]", () => {
      const w = mountBar()
      const inputs = w.findAll("input.price-input")
      expect(inputs).toHaveLength(2)
    })

    it("輸入價格下限 emit update:price-min", async () => {
      const w = mountBar()
      const inputs = w.findAll("input.price-input")
      const minInput = inputs[0]
      await minInput.setValue("5000")
      await minInput.trigger("change")
      expect(w.emitted("update:price-min")).toBeTruthy()
      expect(w.emitted("update:price-min")![0]).toEqual([5000])
    })

    it("輸入價格上限 emit update:price-max", async () => {
      const w = mountBar()
      const inputs = w.findAll("input.price-input")
      const maxInput = inputs[1]
      await maxInput.setValue("15000")
      await maxInput.trigger("change")
      expect(w.emitted("update:price-max")).toBeTruthy()
      expect(w.emitted("update:price-max")![0]).toEqual([15000])
    })

    it("清空價格下限 emit update:price-min(null)", async () => {
      const w = mountBar({ priceMin: 5000 })
      const inputs = w.findAll("input.price-input")
      const minInput = inputs[0]
      await minInput.setValue("")
      await minInput.trigger("change")
      expect(w.emitted("update:price-min")).toBeTruthy()
      expect(w.emitted("update:price-min")![0]).toEqual([null])
    })
  })

  describe("品牌篩選", () => {
    it("渲染品牌 checkbox（availableBrands）", () => {
      const w = mountBar({
        availableBrands: ["金士頓", "美光", "三星"],
        selectedBrands: new Set(["金士頓"]),
      })
      const brandItems = w.findAll(".brand-item")
      expect(brandItems).toHaveLength(3)
    })

    it("無品牌時不渲染品牌區塊", () => {
      const w = mountBar({ availableBrands: [] })
      expect(w.find(".filter-bar__brands").exists()).toBe(false)
    })

    it("有品牌時渲染品牌區塊", () => {
      const w = mountBar({ availableBrands: ["金士頓"] })
      expect(w.find(".filter-bar__brands").exists()).toBe(true)
    })

    it("勾選品牌 emit update:brands", async () => {
      const w = mountBar({ availableBrands: ["金士頓"] })
      const checkbox = w.find(".brand-item input[type='checkbox']")
      await checkbox.trigger("change")
      expect(w.emitted("update:brands")).toBeTruthy()
      expect(w.emitted("update:brands")![0]).toEqual(["金士頓"])
    })
  })

  describe("結果數量", () => {
    it("顯示 resultCount / totalCount", () => {
      const w = mountBar({ resultCount: 5, totalCount: 20 })
      expect(w.find(".result-count").text()).toBe("5 / 20 件商品")
    })
  })

  describe("清除按鈕", () => {
    it("hasActiveFilter=true 時顯示清除按鈕", () => {
      const w = mountBar({ hasActiveFilter: true })
      expect(w.find(".clear-btn").exists()).toBe(true)
    })

    it("hasActiveFilter=false 時隱藏清除按鈕", () => {
      const w = mountBar({ hasActiveFilter: false })
      expect(w.find(".clear-btn").exists()).toBe(false)
    })

    it("點擊清除 emit clear", async () => {
      const w = mountBar({ hasActiveFilter: true })
      await w.find(".clear-btn").trigger("click")
      expect(w.emitted("clear")).toBeTruthy()
      expect(w.emitted("clear")!).toHaveLength(1)
    })
  })
})
