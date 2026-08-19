// web/src/composables/__tests__/useFilters.test.ts — 過濾管線與狀態（契約 v2）
// v2：Item 無 category → 分類維度改以 itemToCategory（itemId→categoryId map）+ categoryId
// 外部對照判定；categoryId 狀態單一來源由呼叫端（useItems.activeCategoryId）注入。
// 驗證：分類→搜尋→條件 AND、clearAll 保留分類、同欄位取代。
import { describe, expect, it } from "vitest"
import { ref, type Ref } from "vue"
import { useFilters } from "@/composables/useFilters"
import { parseCondition } from "@/utils/specFilter"
import { makeItem } from "@/testing/fixtures"
import type { Item } from "@/types/item"

const MAP = {
  "id-MSI RTX 4070 12G OC": "gpu",
  "id-某 8 核 CPU": "cpu",
  "id-某 12G 顯示卡": "gpu",
  "id-某 750W 套裝主機": "desktop",
  "id-XC-5500 隨機贈品主機": "desktop",
}

function fixtureSetup(): { items: Ref<Item[]>; map: Ref<Map<string, string>>; categoryId: Ref<string | null> } {
  const items = ref<Item[]>([
    makeItem({ name: "MSI RTX 4070 12G OC", spec: { vram_gb: 12, wattage_w: 200, chip: "RTX 4070" } }),
    makeItem({ name: "某 8 核 CPU", spec: { cores: 8, tdp_w: 65, socket: "AM5" } }),
    makeItem({ name: "某 12G 顯示卡", spec: { vram_gb: 12, wattage_w: 750, tdp_w: 75 } }),
    makeItem({ name: "某 750W 套裝主機", spec: { wattage_w: 750 } }),
    makeItem({ name: "XC-5500 隨機贈品主機", spec: {} }),
  ])
  const map = ref<Map<string, string>>(new Map(Object.entries(MAP)))
  const categoryId = ref<string | null>(null)
  return { items, map, categoryId }
}

describe("useFilters（v2）", () => {
  it("初始：全部商品、無篩選", () => {
    const { items, map, categoryId } = fixtureSetup()
    const f = useFilters(items, map, categoryId)
    expect(f.filteredItems.value.length).toBe(5)
    expect(f.hasActiveFilter.value).toBe(false)
  })

  it("分類收斂：categoryId='gpu' → 僅顯示卡（外部 itemId→categoryId 對照）", () => {
    const { items, map, categoryId } = fixtureSetup()
    const f = useFilters(items, map, categoryId)
    f.setCategory("gpu")
    expect(f.filteredItems.value.map(i => i.name)).toEqual(["MSI RTX 4070 12G OC", "某 12G 顯示卡"])
  })

  it("分類＋外部 map 連動：map 更新（composable 持有同一 ref）→ 重新過濾", () => {
    const { items, map, categoryId } = fixtureSetup()
    const f = useFilters(items, map, categoryId)
    f.setCategory("desktop")
    expect(f.filteredItems.value.map(i => i.name)).toEqual(["某 750W 套裝主機", "XC-5500 隨機贈品主機"])
    // 模擬 loadAll 後 map 新增（跨分類聚合）：原本未知分類的商品歸入後即可命中
    map.value = new Map([...map.value, ["id-某 8 核 CPU", "desktop"]])
    expect(f.filteredItems.value.map(i => i.name).sort()).toEqual(["某 750W 套裝主機", "某 8 核 CPU", "XC-5500 隨機贈品主機"].sort())
  })

  it("搜尋：keyword 命中 name（trim + lowercase）", () => {
    const { items, map, categoryId } = fixtureSetup()
    const f = useFilters(items, map, categoryId)
    f.setKeyword("  rtx 4070  ")
    expect(f.filteredItems.value.map(i => i.name)).toEqual(["MSI RTX 4070 12G OC"])
    expect(f.hasActiveFilter.value).toBe(true)
  })

  it("規格條件 AND：VRAM≥12G + TDP≥65 交集", () => {
    const { items, map, categoryId } = fixtureSetup()
    const f = useFilters(items, map, categoryId)
    f.addCondition(parseCondition("VRAM≥12G")!)
    f.addCondition(parseCondition("TDP≥65")!)
    expect(f.filteredItems.value.map(i => i.name)).toEqual(["某 12G 顯示卡"])
  })

  it("搜尋×篩選×分類三維度同時收斂", () => {
    const { items, map, categoryId } = fixtureSetup()
    const f = useFilters(items, map, categoryId)
    f.setCategory("gpu")
    f.setKeyword("4070")
    f.addCondition(parseCondition("VRAM≥12G")!)
    expect(f.filteredItems.value.map(i => i.name)).toEqual(["MSI RTX 4070 12G OC"])
  })

  it("同欄位重複套用 → 取代（保留較新值）", () => {
    const { items, map, categoryId } = fixtureSetup()
    const f = useFilters(items, map, categoryId)
    f.addCondition(parseCondition("VRAM≥12G")!)
    f.addCondition(parseCondition("VRAM≥24G")!)
    expect(f.conditions.value.length).toBe(1)
    expect(f.conditions.value[0].value).toBe(24)
    expect(f.filteredItems.value.length).toBe(0) // 無人 ≥24G
  })

  it("removeCondition 移除單一條件 chip", () => {
    const { items, map, categoryId } = fixtureSetup()
    const f = useFilters(items, map, categoryId)
    const c1 = parseCondition("VRAM≥12G")!
    const c2 = parseCondition("TDP≥65")!
    f.addCondition(c1)
    f.addCondition(c2)
    f.removeCondition(c1.id)
    expect(f.conditions.value.map(c => c.field)).toEqual(["tdp_w"])
  })

  it("clearAll 保留目前分類、清空搜尋與條件（BDD #8）", () => {
    const { items, map, categoryId } = fixtureSetup()
    const f = useFilters(items, map, categoryId)
    f.setCategory("gpu")
    f.setKeyword("RTX")
    f.addCondition(parseCondition("VRAM≥12G")!)
    f.clearAll()
    expect(f.keyword.value).toBe("")
    expect(f.conditions.value).toEqual([])
    expect(f.categoryId.value).toBe("gpu")
    // 回到顯示卡分類的完整集合
    expect(f.filteredItems.value.map(i => i.name)).toEqual(["MSI RTX 4070 12G OC", "某 12G 顯示卡"])
  })

  it("clearSearch / clearFilters 個別清除", () => {
    const { items, map, categoryId } = fixtureSetup()
    const f = useFilters(items, map, categoryId)
    f.setKeyword("RTX")
    f.addCondition(parseCondition("VRAM≥12G")!)
    f.clearSearch()
    expect(f.keyword.value).toBe("")
    expect(f.conditions.value.length).toBe(1)
    f.clearFilters()
    expect(f.conditions.value).toEqual([])
  })

  it("僅空白字元視同未搜尋（trim 後 no-op）", () => {
    const { items, map, categoryId } = fixtureSetup()
    const f = useFilters(items, map, categoryId)
    f.setKeyword("   ")
    expect(f.hasActiveFilter.value).toBe(false)
    expect(f.filteredItems.value.length).toBe(5)
  })

  it("無 spec 欄位商品被結構化篩選靜默排除", () => {
    const { items, map, categoryId } = fixtureSetup()
    const f = useFilters(items, map, categoryId)
    f.addCondition(parseCondition("VRAM≥12G")!)
    const names = f.filteredItems.value.map(i => i.name)
    expect(names).not.toContain("XC-5500 隨機贈品主機")
    expect(names).not.toContain("某 8 核 CPU")
  })
})