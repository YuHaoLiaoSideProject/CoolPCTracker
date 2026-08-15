// web/src/composables/__tests__/usePriceHistory.test.ts — BDD E8 三態／E9 最早達成日／E5 單筆
import { describe, expect, it } from "vitest"
import { ref } from "vue"
import type { PricePoint } from "@/types/item"
import {
  usePriceHistory,
  formatDiffAmount,
  formatDiffPercent,
  formatTrendLabel,
} from "@/composables/usePriceHistory"

const h = (pts: [string, number][]): PricePoint[] => pts.map(([d, p]) => ({ d, p }))

describe("usePriceHistory stats（BDD E8 漲跌三態）", () => {
  it("降價：9990 vs 10500 → diff -510、-4.9%、trend=down", () => {
    const { stats } = usePriceHistory(ref(h([["2026-08-14", 10500], ["2026-08-15", 9990]])))
    expect(stats.value.current).toBe(9990)
    expect(stats.value.previous).toBe(10500)
    expect(stats.value.diff).toBe(-510)
    expect(stats.value.diffPercent).toBeCloseTo(-4.857, 1)
    expect(stats.value.trend).toBe("down")
    expect(stats.value.empty).toBe(false)
    expect(stats.value.single).toBe(false)
  })

  it("漲價：1990 vs 1890 → diff +100、+5.3%、trend=up", () => {
    const { stats } = usePriceHistory(ref(h([["2026-08-14", 1890], ["2026-08-15", 1990]])))
    expect(stats.value.diff).toBe(100)
    expect(stats.value.diffPercent).toBeCloseTo(5.291, 1)
    expect(stats.value.trend).toBe("up")
  })

  it("持平：2990 vs 2990 → diff 0、trend=flat", () => {
    const { stats } = usePriceHistory(ref(h([["2026-08-14", 2990], ["2026-08-15", 2990]])))
    expect(stats.value.diff).toBe(0)
    expect(stats.value.diffPercent).toBe(0)
    expect(stats.value.trend).toBe("flat")
  })

  it("history 空 → 全 null、empty=true", () => {
    const { stats } = usePriceHistory(ref<PricePoint[]>([]))
    expect(stats.value.empty).toBe(true)
    expect(stats.value.current).toBeNull()
    expect(stats.value.previous).toBeNull()
    expect(stats.value.diff).toBeNull()
    expect(stats.value.trend).toBeNull()
    expect(stats.value.low).toBeNull()
    expect(stats.value.lowDate).toBeNull()
  })

  it("僅一筆（E5）→ previous/diff/trend 全 null、single=true、low=目前價", () => {
    const { stats } = usePriceHistory(ref(h([["2026-08-15", 5990]])))
    expect(stats.value.single).toBe(true)
    expect(stats.value.current).toBe(5990)
    expect(stats.value.previous).toBeNull()
    expect(stats.value.diff).toBeNull()
    expect(stats.value.diffPercent).toBeNull()
    expect(stats.value.trend).toBeNull()
    expect(stats.value.low).toBe(5990)
    expect(stats.value.lowDate).toBe("2026-08-15")
  })

  it("歷史最低：取 min 與最早達成日（E9：連續三日同為最低 → 最早日）", () => {
    const { stats } = usePriceHistory(
      ref(h([
        ["2026-08-10", 4500],
        ["2026-08-11", 4500],
        ["2026-08-12", 4500],
        ["2026-08-13", 4800],
        ["2026-08-14", 4800],
        ["2026-08-15", 4800],
      ])),
    )
    expect(stats.value.low).toBe(4500)
    expect(stats.value.lowDate).toBe("2026-08-10") // 最早達成日
  })

  it("多日不同價時最低日亦正確", () => {
    const { stats } = usePriceHistory(
      ref(h([["2026-08-13", 9490], ["2026-08-14", 9490], ["2026-08-15", 9290]])),
    )
    expect(stats.value.low).toBe(9290)
    expect(stats.value.lowDate).toBe("2026-08-15")
  })
})

describe("格式化 util（BDD E8 標籤）", () => {
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

  it("formatTrendLabel：完整標籤（BDD Examples 原樣）", () => {
    expect(formatTrendLabel(-510, 10500)).toBe("降價 NT$510（-4.9%）")
    expect(formatTrendLabel(100, 1890)).toBe("漲價 NT$100（+5.3%）")
    expect(formatTrendLabel(0, 2990)).toBe("持平")
  })
})

describe("chartSeries", () => {
  it("日期/價格陣列與 history 對齊", () => {
    const { chartSeries } = usePriceHistory(
      ref(h([["2026-08-13", 9490], ["2026-08-15", 9290]])),
    )
    expect(chartSeries.value.dates).toEqual(["2026-08-13", "2026-08-15"])
    expect(chartSeries.value.prices).toEqual([9490, 9290])
  })
})
