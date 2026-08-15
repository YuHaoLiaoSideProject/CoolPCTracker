// web/src/utils/__tests__/format.test.ts — formatPrice / formatDateTime（台北時間）
import { describe, expect, it } from "vitest"
import { formatPrice, formatNumber, formatDateTime, formatDate } from "@/utils/format"

describe("formatPrice", () => {
  it("NT$ + 千分位", () => {
    expect(formatPrice(28990)).toBe("NT$ 28,990")
    expect(formatPrice(999)).toBe("NT$ 999")
    expect(formatPrice(0)).toBe("NT$ 0")
  })
})

describe("formatNumber", () => {
  it("千分位", () => {
    expect(formatNumber(10500)).toBe("10,500")
    expect(formatNumber(500)).toBe("500")
  })
})

describe("formatDateTime / formatDate（台北時間 UTC+8）", () => {
  it("UTC ISO → 台北時間日期時間", () => {
    // 2026-08-15T06:00:00Z = 台北 2026/8/15 14:00
    const s = formatDateTime("2026-08-15T06:00:00Z")
    expect(s).toContain("2026/8/15")
    expect(s).toContain("14:00")
  })

  it("formatDate 僅日期", () => {
    expect(formatDate("2026-08-15T06:00:00Z")).toBe("2026/8/15")
  })

  it("空值/非法輸入不拋錯", () => {
    expect(formatDateTime(undefined)).toBe("未知")
    expect(formatDateTime("not-a-date")).toBe("not-a-date")
  })
})
