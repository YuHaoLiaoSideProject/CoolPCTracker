// web/src/utils/__tests__/specFilter.test.ts — parseCondition / matchesCondition
// （開發規格 003 §2.6：≥ 語意含邊界、缺欄位靜默排除、未知欄位回 null）
import { describe, expect, it } from "vitest"
import { parseCondition, matchesCondition, SPEC_FIELD_LABELS } from "@/utils/specFilter"
import { makeItem } from "@/testing/fixtures"

describe("parseCondition", () => {
  it("VRAM≥12G → vram_gb/12/G", () => {
    const c = parseCondition("VRAM≥12G")
    expect(c).not.toBeNull()
    expect(c).toMatchObject({ field: "vram_gb", op: ">=", value: 12, unit: "G" })
    expect(c!.label).toBe("VRAM≥12G")
  })

  it("瓦數≥750W → wattage_w/750/W", () => {
    const c = parseCondition("瓦數≥750W")
    expect(c).toMatchObject({ field: "wattage_w", value: 750, unit: "W" })
  })

  it("CPU核數≥8 → cores/8（輸入無單位 → unit 依規格為空字串）", () => {
    const c = parseCondition("CPU核數≥8")
    expect(c).toMatchObject({ field: "cores", value: 8, unit: "" })
    expect(c!.label).toBe("CPU核數≥8")
  })

  it("接受 >= 與空白（UI 統一轉 ≥）", () => {
    const c = parseCondition("VRAM >= 12G")
    expect(c).toMatchObject({ field: "vram_gb", value: 12 })
  })

  it("小數門檻", () => {
    const c = parseCondition("VRAM≥11.5G")
    expect(c).toMatchObject({ value: 11.5 })
  })

  it("未知欄位 → null", () => {
    expect(parseCondition("螢幕≥24")).toBeNull()
    expect(parseCondition("機殼≥3")).toBeNull()
  })

  it("格式不符 → null", () => {
    expect(parseCondition("VRAM")).toBeNull()
    expect(parseCondition("≥12")).toBeNull()
    expect(parseCondition("")).toBeNull()
    expect(parseCondition("VRAM≥")).toBeNull()
  })

  it("SPEC_FIELD_LABELS 對照完整（P1 三欄位 + P2 擴充）", () => {
    expect(SPEC_FIELD_LABELS.vram_gb.label).toBe("VRAM")
    expect(SPEC_FIELD_LABELS.cores.label).toBe("CPU核數")
    expect(SPEC_FIELD_LABELS.wattage_w.label).toBe("瓦數")
    expect(SPEC_FIELD_LABELS.capacity_gb.label).toBe("容量")
    expect(SPEC_FIELD_LABELS.ram_gb.label).toBe("記憶體")
    expect(SPEC_FIELD_LABELS.tdp_w.label).toBe("TDP")
  })
})

describe("matchesCondition", () => {
  it("邊界值納入：12G 命中 VRAM≥12G、8 核命中 ≥8、750W 命中 ≥750W", () => {
    const cond12 = parseCondition("VRAM≥12G")!
    const gpu12 = makeItem({ name: "某 12G 顯示卡", spec: { vram_gb: 12 } })
    expect(matchesCondition(gpu12, cond12)).toBe(true)

    const cond8 = parseCondition("CPU核數≥8")!
    const cpu8 = makeItem({ name: "某 8 核 CPU", category: "CPU", spec: { cores: 8 } })
    expect(matchesCondition(cpu8, cond8)).toBe(true)

    const cond750 = parseCondition("瓦數≥750W")!
    const psu750 = makeItem({ name: "某 750W 套裝主機", category: "套裝/準系統", spec: { wattage_w: 750 } })
    expect(matchesCondition(psu750, cond750)).toBe(true)
  })

  it("低於門檻不命中", () => {
    const cond = parseCondition("VRAM≥12G")!
    const gpu8 = makeItem({ name: "8G 卡", spec: { vram_gb: 8 } })
    expect(matchesCondition(gpu8, cond)).toBe(false)
  })

  it("缺欄位（spec 空物件）靜默排除不報錯", () => {
    const cond = parseCondition("VRAM≥12G")!
    const noSpec = makeItem({ name: "XC-5500 隨機贈品主機", spec: {} })
    expect(() => matchesCondition(noSpec, cond)).not.toThrow()
    expect(matchesCondition(noSpec, cond)).toBe(false)
  })

  it("欄位存在但非數值 → false（不命中）", () => {
    const cond = parseCondition("CPU核數≥8")!
    const it = makeItem({ name: "怪商品", spec: { cores: "八" as unknown as number } })
    expect(matchesCondition(it, cond)).toBe(false)
  })
})
