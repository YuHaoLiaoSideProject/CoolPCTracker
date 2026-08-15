// web/src/components/__tests__/SpecTable.test.ts — BDD E10 空值欄位不渲染
import { describe, expect, it } from "vitest"
import { mount } from "@vue/test-utils"
import SpecTable from "@/components/SpecTable.vue"

describe("SpecTable", () => {
  it("渲染有值欄位：欄位名：值，key 轉中文（SPEC_LABELS）", () => {
    const w = mount(SpecTable, {
      props: { spec: { brand: "Intel", cores: 14, base_ghz: 3.5, tdp_w: 125, socket: "LGA1700" } },
    })
    const keys = w.findAll(".spec-key").map((n) => n.text())
    const vals = w.findAll(".spec-value").map((n) => n.text())
    expect(keys).toEqual(["品牌", "核心數", "基礎時脈(GHz)", "功耗 TDP(W)", "腳位"])
    expect(vals).toEqual(["Intel", "14", "3.5", "125", "LGA1700"])
  })

  it("空值欄位（null/undefined/''）整列不渲染（E10：turbo_ghz 缺席）", () => {
    const w = mount(SpecTable, {
      props: { spec: { brand: "AMD", model: "R7 7700", turbo_ghz: undefined, cores: 8 } },
    })
    const keys = w.findAll(".spec-key").map((n) => n.text())
    expect(keys).not.toContain("超頻時脈(GHz)")
    expect(keys).toContain("型號")
    // 有值欄位數正確（3 筆）
    expect(keys).toHaveLength(3)
  })

  it("空字串值也視為空值不渲染", () => {
    const w = mount(SpecTable, { props: { spec: { brand: "", model: "X" } } })
    expect(w.findAll(".spec-key").map((n) => n.text())).toEqual(["型號"])
  })

  it("未知 key 顯示原始 key（fallback）", () => {
    const w = mount(SpecTable, { props: { spec: { mystery_field: "foo" } } })
    expect(w.find(".spec-key").text()).toBe("mystery_field")
  })

  it("全部空值 → 顯示「無規格資訊」", () => {
    const w = mount(SpecTable, { props: { spec: { a: undefined, b: "" } } })
    expect(w.text()).toContain("無規格資訊")
    expect(w.find(".spec-table").exists()).toBe(false)
  })
})
