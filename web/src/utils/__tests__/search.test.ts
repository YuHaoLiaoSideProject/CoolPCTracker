// web/src/utils/__tests__/search.test.ts — matchesKeyword（開發規格 003 §2.6 / §6.3）
import { describe, expect, it } from "vitest"
import { matchesKeyword } from "@/utils/search"
import { makeItem } from "@/testing/fixtures"

const base = makeItem({ name: "MSI RTX 4070 VENTUS 2X 12G OC", spec: { vram_gb: 12, chip: "RTX 4070" } })

describe("matchesKeyword", () => {
  it("名稱子字串命中（不區分大小寫）", () => {
    expect(matchesKeyword(base, "rtx 4070")).toBe(true)
    expect(matchesKeyword(base, "MSI")).toBe(true)
  })

  it("spec 欄位值命中（如 LGA1700 socket）", () => {
    const it = makeItem({ name: "技嘉 B760M", category: "主機板", spec: { socket: "LGA1700" } })
    expect(matchesKeyword(it, "lga1700")).toBe(true)
  })

  it("僅比對 name + spec，不含 history（搜尋 9999 不命中歷史價 9999）", () => {
    const it = makeItem({
      name: "XC-5500 隨機贈品主機",
      spec: {},
      history: [
        { d: "2026-08-13", p: 9999 },
        { d: "2026-08-15", p: 7990 },
      ],
    })
    expect(matchesKeyword(it, "9999")).toBe(false)
    expect(matchesKeyword(it, "xc-5500")).toBe(true) // 名稱仍命中
  })

  it("不含 flags / status 欄位", () => {
    const it = makeItem({ name: "某商品", flags: { hot: true, promo: "任搭↓500" }, status: "gone" })
    expect(matchesKeyword(it, "hot")).toBe(false)
    expect(matchesKeyword(it, "任搭")).toBe(false)
    expect(matchesKeyword(it, "gone")).toBe(false)
  })

  it("無 spec 欄位商品仍可被名稱搜尋命中（spec join 為空不影響）", () => {
    const it = makeItem({ name: "XC-5500 隨機贈品主機", spec: {} })
    expect(matchesKeyword(it, "xc-5500")).toBe(true)
  })

  it("特殊字元字面比對不拋錯（非 regex）", () => {
    const it = makeItem({ name: "【劈發價】RTX 4070 & i5 組合", spec: {} })
    expect(() => matchesKeyword(it, "RTX+4070 & 12G≥")).not.toThrow()
    expect(matchesKeyword(it, "4070 & i5")).toBe(true)
    expect(matchesKeyword(it, "RTX+4070 & 12G≥")).toBe(false)
  })

  it("無關鍵字（空字串）時回傳 true 語意：q 為空不呼叫（useFilters 已 guard）", () => {
    expect(matchesKeyword(base, "")).toBe(true)
  })
})
