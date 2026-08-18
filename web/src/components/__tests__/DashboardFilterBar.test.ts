// web/src/components/__tests__/DashboardFilterBar.test.ts — DashboardFilterBar 單元測試（022）
import { describe, expect, it } from "vitest"
import { mount } from "@vue/test-utils"
import DashboardFilterBar from "@/components/DashboardFilterBar.vue"
import type { SortMode } from "@/types/dashboardFilter"

// ── Helpers ──

function makeProps(overrides?: Record<string, unknown>) {
  return {
    sortMode: "price_asc" as SortMode,
    priceMin: null,
    priceMax: null,
    availableBrands: [] as string[],
    selectedBrands: new Set<string>(),
    availableCapacities: [] as string[],
    selectedCapacities: new Set<string>(),
    availableRpms: [] as string[],
    selectedRpms: new Set<string>(),
    availableRamCapacities: [] as string[],
    selectedRamCapacities: new Set<string>(),
    availableDdrTypes: [] as string[],
    selectedDdrTypes: new Set<string>(),
    availableInterfaces: [] as string[],
    selectedInterfaces: new Set<string>(),
    categoryName: null as string | null,
    resultCount: 10,
    totalCount: 10,
    hasActiveFilter: false,
    ...overrides,
  }
}

function mountBar(propsOverrides?: Record<string, unknown>) {
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

    it("勾選品牌 emit update:brands", async () => {
      const w = mountBar({ availableBrands: ["金士頓", "三星"] })
      const checkbox = w.find(".brand-item input[type='checkbox']")
      await checkbox.trigger("change")
      expect(w.emitted("update:brands")).toBeTruthy()
      expect(w.emitted("update:brands")![0]).toEqual(["金士頓"])
    })
  })

  describe("容量篩選", () => {
    it("categoryName='記憶卡' 時渲染容量篩選", () => {
      const w = mountBar({
        categoryName: "記憶卡",
        availableCapacities: ["64GB", "128GB", "256GB"],
      })
      expect(w.find(".filter-bar__capacities").exists()).toBe(true)
      expect(w.findAll(".capacity-item")).toHaveLength(3)
    })

    it("categoryName='HDD' 時渲染容量篩選", () => {
      const w = mountBar({
        categoryName: "HDD",
        availableCapacities: ["1TB", "2TB", "4TB"],
      })
      expect(w.find(".filter-bar__capacities").exists()).toBe(true)
      expect(w.findAll(".capacity-item")).toHaveLength(3)
    })

    it("categoryName='SSD' 時渲染容量篩選", () => {
      const w = mountBar({
        categoryName: "SSD",
        availableCapacities: ["512GB", "1TB", "2TB"],
      })
      expect(w.find(".filter-bar__capacities").exists()).toBe(true)
      expect(w.findAll(".capacity-item")).toHaveLength(3)
    })

    it("categoryName 非 SSD/HDD/記憶卡 時不渲染容量篩選", () => {
      const w = mountBar({
        categoryName: "顯示卡",
        availableCapacities: ["8GB", "12GB"],
      })
      expect(w.find(".filter-bar__capacities").exists()).toBe(false)
    })

    it("categoryName='記憶卡' 時渲染容量篩選和品牌", () => {
      const w = mountBar({
        categoryName: "記憶卡",
        availableCapacities: ["64GB"],
        availableBrands: ["三星", "金士頓"],
      })
      expect(w.find(".filter-bar__brands").exists()).toBe(true)
      expect(w.find(".filter-bar__capacities").exists()).toBe(true)
    })

    it("categoryName='HDD' 時渲染容量篩選和品牌", () => {
      const w = mountBar({
        categoryName: "HDD",
        availableCapacities: ["1TB", "2TB"],
        availableBrands: ["Seagate", "WD"],
      })
      expect(w.find(".filter-bar__brands").exists()).toBe(true)
      expect(w.find(".filter-bar__capacities").exists()).toBe(true)
    })

    it("勾選容量 emit update:capacities", async () => {
      const w = mountBar({
        categoryName: "記憶卡",
        availableCapacities: ["64GB", "128GB"],
      })
      const checkbox = w.find(".capacity-item input[type='checkbox']")
      await checkbox.trigger("change")
      expect(w.emitted("update:capacities")).toBeTruthy()
      expect(w.emitted("update:capacities")![0]).toEqual(["64GB"])
    })

    it("無容量時不渲染容量區塊", () => {
      const w = mountBar({
        categoryName: "記憶卡",
        availableCapacities: [],
      })
      expect(w.find(".filter-bar__capacities").exists()).toBe(false)
    })
  })

  describe("轉速篩選（HDD 專用）", () => {
    it("categoryName='HDD' 時渲染轉速篩選", () => {
      const w = mountBar({
        categoryName: "HDD",
        availableRpms: ["5400RPM", "7200RPM"],
      })
      expect(w.find(".filter-bar__rpms").exists()).toBe(true)
      expect(w.findAll(".rpm-item")).toHaveLength(2)
    })

    it("categoryName 非 HDD 時不渲染轉速篩選", () => {
      const w = mountBar({
        categoryName: "SSD",
        availableRpms: ["5400RPM", "7200RPM"],
      })
      expect(w.find(".filter-bar__rpms").exists()).toBe(false)
    })

    it("勾選轉速 emit update:rpms", async () => {
      const w = mountBar({
        categoryName: "HDD",
        availableRpms: ["5400RPM", "7200RPM"],
      })
      const checkbox = w.find(".rpm-item input[type='checkbox']")
      await checkbox.trigger("change")
      expect(w.emitted("update:rpms")).toBeTruthy()
      expect(w.emitted("update:rpms")![0]).toEqual(["5400RPM"])
    })

    it("無轉速時不渲染轉速區塊", () => {
      const w = mountBar({
        categoryName: "HDD",
        availableRpms: [],
      })
      expect(w.find(".filter-bar__rpms").exists()).toBe(false)
    })
  })

  describe("記憶體篩選", () => {
    it("categoryName='記憶體' 時渲染容量篩選", () => {
      const w = mountBar({
        categoryName: "記憶體",
        availableRamCapacities: ["8GB", "16GB", "32GB"],
      })
      expect(w.find(".filter-bar__ram-capacities").exists()).toBe(true)
      expect(w.findAll(".ram-capacity-item")).toHaveLength(3)
    })

    it("categoryName='記憶體' 時渲染 DDR 類型篩選", () => {
      const w = mountBar({
        categoryName: "記憶體",
        availableDdrTypes: ["DDR4", "DDR5"],
      })
      expect(w.find(".filter-bar__ddr-types").exists()).toBe(true)
      expect(w.findAll(".ddr-type-item")).toHaveLength(2)
    })

    it("categoryName 非記憶體 時不渲染記憶體篩選", () => {
      const w = mountBar({
        categoryName: "SSD",
        availableRamCapacities: ["8GB"],
        availableDdrTypes: ["DDR4"],
      })
      expect(w.find(".filter-bar__ram-capacities").exists()).toBe(false)
      expect(w.find(".filter-bar__ddr-types").exists()).toBe(false)
    })
  })

  describe("SSD 介面篩選", () => {
    it("categoryName='SSD' 時渲染介面篩選", () => {
      const w = mountBar({
        categoryName: "SSD",
        availableInterfaces: ["NVMe", "SATA"],
      })
      expect(w.find(".filter-bar__interfaces").exists()).toBe(true)
      expect(w.findAll(".interface-item")).toHaveLength(2)
    })

    it("categoryName 非 SSD 時不渲染介面篩選", () => {
      const w = mountBar({
        categoryName: "HDD",
        availableInterfaces: ["NVMe", "SATA"],
      })
      expect(w.find(".filter-bar__interfaces").exists()).toBe(false)
    })
  })

  describe("清除篩選", () => {
    it("hasActiveFilter=true 時渲染清除按鈕", () => {
      const w = mountBar({ hasActiveFilter: true })
      expect(w.find(".clear-btn").exists()).toBe(true)
    })

    it("hasActiveFilter=false 時不渲染清除按鈕", () => {
      const w = mountBar({ hasActiveFilter: false })
      expect(w.find(".clear-btn").exists()).toBe(false)
    })

    it("點擊清除按鈕 emit clear", async () => {
      const w = mountBar({ hasActiveFilter: true })
      await w.find(".clear-btn").trigger("click")
      expect(w.emitted("clear")).toBeTruthy()
    })
  })

  describe("結果計數", () => {
    it("顯示 resultCount / totalCount", () => {
      const w = mountBar({ resultCount: 5, totalCount: 20 })
      expect(w.find(".result-count").text()).toBe("5 / 20 件商品")
    })
  })
})
