// web/src/composables/__tests__/useFilters.test.ts — 過濾管線與狀態
// （開發規格 003 §2.5：分類→搜尋→條件 AND、clearAll 保留分類、同欄位取代）
import { describe, expect, it } from "vitest"
import { ref } from "vue"
import { useFilters } from "@/composables/useFilters"
import { parseCondition } from "@/utils/specFilter"
import { makeItem } from "@/testing/fixtures"
import type { Item } from "@/types/item"

function fixtureItems(): Item[] {
  return [
    makeItem({
      name: "MSI RTX 4070 12G OC",
      spec: { vram_gb: 12, wattage_w: 200, chip: "RTX 4070" },
    }),
    makeItem({
      name: "某 8 核 CPU",
      category: "CPU",
      spec: { cores: 8, tdp_w: 65, socket: "AM5" },
    }),
    makeItem({
      name: "某 12G 顯示卡",
      spec: { vram_gb: 12, wattage_w: 750 },
    }),
    makeItem({
      name: "某 750W 套裝主機",
      category: "套裝/準系統",
      spec: { wattage_w: 750 },
    }),
    makeItem({ name: "XC-5500 隨機贈品主機", category: "套裝/準系統", spec: {} }),
  ]
}

describe("useFilters", () => {
  it("初始：全部商品、無篩選", () => {
    const f = useFilters(ref(fixtureItems()))
    expect(f.filteredItems.value.length).toBe(5)
    expect(f.hasActiveFilter.value).toBe(false)
  })

  it("分類收斂：category=GPU → 僅顯示卡（label 對照）", () => {
    const f = useFilters(ref(fixtureItems()))
    f.setCategory("GPU")
    expect(f.filteredItems.value.map(i => i.name)).toEqual(["MSI RTX 4070 12G OC", "某 12G 顯示卡"])
  })

  it("搜尋：keyword 命中 name（trim + lowercase）", () => {
    const f = useFilters(ref(fixtureItems()))
    f.setKeyword("  rtx 4070  ")
    expect(f.filteredItems.value.map(i => i.name)).toEqual(["MSI RTX 4070 12G OC"])
    expect(f.hasActiveFilter.value).toBe(true)
  })

  it("規格條件 AND：VRAM≥12G + 瓦數≥750W 交集", () => {
    const f = useFilters(ref(fixtureItems()))
    f.addCondition(parseCondition("VRAM≥12G")!)
    f.addCondition(parseCondition("瓦數≥750W")!)
    expect(f.filteredItems.value.map(i => i.name)).toEqual(["某 12G 顯示卡"])
  })

  it("搜尋×篩選×分類三維度同時收斂", () => {
    const f = useFilters(ref(fixtureItems()))
    f.setCategory("GPU")
    f.setKeyword("4070")
    f.addCondition(parseCondition("VRAM≥12G")!)
    expect(f.filteredItems.value.map(i => i.name)).toEqual(["MSI RTX 4070 12G OC"])
  })

  it("同欄位重複套用 → 取代（保留較新值）", () => {
    const f = useFilters(ref(fixtureItems()))
    f.addCondition(parseCondition("VRAM≥12G")!)
    f.addCondition(parseCondition("VRAM≥24G")!)
    expect(f.conditions.value.length).toBe(1)
    expect(f.conditions.value[0].value).toBe(24)
    expect(f.filteredItems.value.length).toBe(0) // 無人 ≥24G
  })

  it("removeCondition 移除單一條件 chip", () => {
    const f = useFilters(ref(fixtureItems()))
    const c1 = parseCondition("VRAM≥12G")!
    const c2 = parseCondition("瓦數≥750W")!
    f.addCondition(c1)
    f.addCondition(c2)
    f.removeCondition(c1.id)
    expect(f.conditions.value.map(c => c.field)).toEqual(["wattage_w"])
  })

  it("clearAll 保留目前分類、清空搜尋與條件（BDD #8）", () => {
    const f = useFilters(ref(fixtureItems()))
    f.setCategory("GPU")
    f.setKeyword("RTX")
    f.addCondition(parseCondition("VRAM≥12G")!)
    f.clearAll()
    expect(f.keyword.value).toBe("")
    expect(f.conditions.value).toEqual([])
    expect(f.categoryKey.value).toBe("GPU")
    // 回到顯示卡分類的完整集合
    expect(f.filteredItems.value.map(i => i.name)).toEqual(["MSI RTX 4070 12G OC", "某 12G 顯示卡"])
  })

  it("clearSearch / clearFilters 個別清除", () => {
    const f = useFilters(ref(fixtureItems()))
    f.setKeyword("RTX")
    f.addCondition(parseCondition("VRAM≥12G")!)
    f.clearSearch()
    expect(f.keyword.value).toBe("")
    expect(f.conditions.value.length).toBe(1)
    f.clearFilters()
    expect(f.conditions.value).toEqual([])
  })

  it("僅空白字元視同未搜尋（trim 後 no-op）", () => {
    const f = useFilters(ref(fixtureItems()))
    f.setKeyword("   ")
    expect(f.hasActiveFilter.value).toBe(false)
    expect(f.filteredItems.value.length).toBe(5)
  })

  it("無 spec 欄位商品被結構化篩選靜默排除", () => {
    const f = useFilters(ref(fixtureItems()))
    f.addCondition(parseCondition("VRAM≥12G")!)
    const names = f.filteredItems.value.map(i => i.name)
    expect(names).not.toContain("XC-5500 隨機贈品主機")
    expect(names).not.toContain("某 8 核 CPU")
  })
})
