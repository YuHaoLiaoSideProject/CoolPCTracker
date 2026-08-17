// web/src/lib/__tests__/priceChange.test.ts — 漲跌計算共用純函數（003 卡片 / 004 詳情頁共用）
// 覆蓋：三態（漲/跌/持平）、單點「新」、空 history「—」、多筆取最後兩點、
//       非連續日（與「上一筆有紀錄的日期」比較）、百分比、badge 文字/class、詳情頁格式化 util。
import { describe, expect, it } from "vitest"
import type { PricePoint } from "@/types/item"
import {
  computePriceChange,
  formatDiffAmount,
  formatDiffPercent,
  formatTrendLabel,
  priceChangeBadgeClass,
  priceChangeBadgeText,
} from "@/lib/priceChange"

const mk = (pts: [string, number][]): PricePoint[] => pts.map(([d, p]) => ({ d, p }))

describe("computePriceChange（最後兩筆計算漲跌幅）", () => {
  it("漲：10500 vs 10000 → diff +500、trend=up、previousDate 帶回", () => {
    const c = computePriceChange(mk([["2026-08-14", 10000], ["2026-08-15", 10500]]))
    expect(c.current).toBe(10500)
    expect(c.currentDate).toBe("2026-08-15")
    expect(c.previous).toBe(10000)
    expect(c.previousDate).toBe("2026-08-14")
    expect(c.diff).toBe(500)
    expect(c.trend).toBe("up")
    expect(c.hasPrevious).toBe(true)
  })

  it("跌：7500 vs 8000 → diff -500、trend=down", () => {
    const c = computePriceChange(mk([["2026-08-14", 8000], ["2026-08-15", 7500]]))
    expect(c.diff).toBe(-500)
    expect(c.diffPercent).toBeCloseTo(-6.25, 2)
    expect(c.trend).toBe("down")
  })

  it("持平：20000 vs 20000 → diff 0、trend=flat、diffPercent 0", () => {
    const c = computePriceChange(mk([["2026-08-14", 20000], ["2026-08-15", 20000]]))
    expect(c.diff).toBe(0)
    expect(c.diffPercent).toBe(0)
    expect(c.trend).toBe("flat")
  })

  it("多筆 history → 只取最後兩點（中間點不參與）", () => {
    const c = computePriceChange(mk([["2026-08-12", 9000], ["2026-08-13", 9999], ["2026-08-14", 9500], ["2026-08-15", 10000]]))
    expect(c.current).toBe(10000)
    expect(c.previous).toBe(9500) // 倒數第二筆，非 9999
    expect(c.diff).toBe(500)
  })

  it("非連續日：最後兩點相隔 >1 天（08-10 → 08-15）仍以「上一筆有紀錄的日期」比較", () => {
    const c = computePriceChange(mk([["2026-08-10", 3490], ["2026-08-15", 2990]]))
    expect(c.previousDate).toBe("2026-08-10") // 不是日曆昨日 08-14
    expect(c.previous).toBe(3490)
    expect(c.diff).toBe(-500)
    expect(c.trend).toBe("down")
  })

  it("僅 1 筆（首日追蹤）→ previous/diff/diffPercent/trend 全 null、hasPrevious=false（不壞）", () => {
    const c = computePriceChange(mk([["2026-08-15", 5990]]))
    expect(c.current).toBe(5990)
    expect(c.currentDate).toBe("2026-08-15")
    expect(c.previous).toBeNull()
    expect(c.previousDate).toBeNull()
    expect(c.diff).toBeNull()
    expect(c.diffPercent).toBeNull()
    expect(c.trend).toBeNull()
    expect(c.hasPrevious).toBe(false)
  })

  it("空 history → 全 null、hasPrevious=false（不 throw）", () => {
    const c = computePriceChange([])
    expect(c.current).toBeNull()
    expect(c.currentDate).toBeNull()
    expect(c.previous).toBeNull()
    expect(c.diff).toBeNull()
    expect(c.trend).toBeNull()
    expect(c.hasPrevious).toBe(false)
  })
})

describe("priceChangeBadgeText（卡片 badge 文字）", () => {
  it("漲/跌/持平：金額取絕對值、千分位", () => {
    expect(priceChangeBadgeText(computePriceChange(mk([["2026-08-14", 10000], ["2026-08-15", 10500]])))).toBe("漲 500")
    expect(priceChangeBadgeText(computePriceChange(mk([["2026-08-14", 10500], ["2026-08-15", 9990]])))).toBe("跌 510")
    expect(priceChangeBadgeText(computePriceChange(mk([["2026-08-14", 20000], ["2026-08-15", 20000]])))).toBe("持平")
    expect(priceChangeBadgeText(computePriceChange(mk([["2026-08-14", 100000], ["2026-08-15", 101000]])))).toBe("漲 1,000")
  })

  it("僅 1 筆（有價無前）→「新」", () => {
    expect(priceChangeBadgeText(computePriceChange(mk([["2026-08-15", 5990]])))).toBe("新")
  })

  it("空 history（無價）→「—」", () => {
    expect(priceChangeBadgeText(computePriceChange([]))).toBe("—")
  })
})

describe("priceChangeBadgeClass（badge 配色 class）", () => {
  it("漲紅/跌綠/持平灰", () => {
    expect(priceChangeBadgeClass(computePriceChange(mk([["2026-08-14", 10000], ["2026-08-15", 10500]])))).toBe("price-up")
    expect(priceChangeBadgeClass(computePriceChange(mk([["2026-08-14", 10500], ["2026-08-15", 9990]])))).toBe("price-down")
    expect(priceChangeBadgeClass(computePriceChange(mk([["2026-08-14", 20000], ["2026-08-15", 20000]])))).toBe("price-flat")
  })

  it("僅 1 筆 → price-new（中性色）；空 history → 無 class", () => {
    expect(priceChangeBadgeClass(computePriceChange(mk([["2026-08-15", 5990]])))).toBe("price-new")
    expect(priceChangeBadgeClass(computePriceChange([]))).toBe("")
  })
})

describe("詳情頁格式化 util（由 usePriceHistory 移至共用 lib）", () => {
  it("formatDiffAmount：降價/漲價金額（取絕對值、千分位）", () => {
    expect(formatDiffAmount(-510)).toBe("降價 NT$510")
    expect(formatDiffAmount(100)).toBe("漲價 NT$100")
    expect(formatDiffAmount(-5100)).toBe("降價 NT$5,100")
  })

  it("formatDiffPercent：帶符號 1 位小數", () => {
    expect(formatDiffPercent(-510, 10500)).toBe("-4.9%")
    expect(formatDiffPercent(100, 1890)).toBe("+5.3%")
    expect(formatDiffPercent(0, 2990)).toBe("0.0%")
  })

  it("formatTrendLabel：完整標籤（004 BDD Examples 原樣）", () => {
    expect(formatTrendLabel(-510, 10500)).toBe("降價 NT$510（-4.9%）")
    expect(formatTrendLabel(100, 1890)).toBe("漲價 NT$100（+5.3%）")
    expect(formatTrendLabel(0, 2990)).toBe("持平")
  })
})
