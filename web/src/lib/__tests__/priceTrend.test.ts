// web/src/lib/__tests__/priceTrend.test.ts — 價格走勢圖純函數（組態/資料轉換）單測
// 不 mount 元件、不 mock lightweight-charts（純函數不碰 canvas）。
import { describe, expect, it } from "vitest"
import { LineStyle } from "@/lib/lightweight-charts"
import type { Time } from "@/lib/lightweight-charts"
import {
  buildChartOptions,
  buildMarkers,
  buildPriceLineOptions,
  buildSeriesData,
  computeTooltipPosition,
  formatChartDate,
} from "@/lib/priceTrend"
import type { PricePoint } from "@/types/item"

const mk = (pts: [string, number][]): PricePoint[] => pts.map(([d, p]) => ({ d, p }))

describe("buildSeriesData", () => {
  it("PricePoint[] → { time, value }[]，time 為 'yyyy-mm-dd' 字串（非毫秒/秒 timestamp）", () => {
    expect(buildSeriesData(mk([["2026-08-13", 9490], ["2026-08-15", 9290]]))).toEqual([
      { time: "2026-08-13", value: 9490 },
      { time: "2026-08-15", value: 9290 },
    ])
  })
})

describe("buildMarkers", () => {
  it("≤24 點 → 每點一個 circle marker（position inBar）", () => {
    const history = mk([["2026-08-13", 9490], ["2026-08-15", 9290]])
    const markers = buildMarkers(history)
    expect(markers).toHaveLength(2)
    expect(markers[0]).toMatchObject({ time: "2026-08-13", position: "inBar", shape: "circle" })
  })

  it("單筆 → circle marker 附價格文字 NT$5,990", () => {
    const markers = buildMarkers(mk([["2026-08-15", 5990]]))
    expect(markers).toHaveLength(1)
    expect(markers[0]).toMatchObject({ shape: "circle" })
    expect(markers[0].text).toBe("NT$5,990")
  })

  it(">24 點 → 不顯示資料點符號（空陣列）", () => {
    const pts: [string, number][] = Array.from({ length: 25 }, (_, i) => [
      `2026-07-${String(1 + i).padStart(2, "0")}`,
      5000 + i,
    ])
    expect(buildMarkers(mk(pts))).toEqual([])
  })
})

describe("buildPriceLineOptions", () => {
  it("目標價線：dashed #f59e0b、lineWidth 2、價格軸 title「目標價」", () => {
    const line = buildPriceLineOptions(9500)
    expect(line.price).toBe(9500)
    expect(line.color).toBe("#f59e0b")
    expect(line.lineStyle).toBe(LineStyle.Dashed)
    expect(line.lineWidth).toBe(2)
    expect(line.title).toBe("目標價")
    expect(line.axisLabelVisible).toBe(true)
  })
})

describe("buildChartOptions", () => {
  it("價格軸 NT$ 千分位、時間軸 MM-dd、透明背景＋硬編碼 token 色", () => {
    const opts = buildChartOptions({ width: 600, height: 360 })
    expect(opts.width).toBe(600)
    expect(opts.height).toBe(360)
    expect(opts.layout?.background).toMatchObject({ type: "solid", color: "transparent" })
    expect(opts.layout?.textColor).toBe("#1f2937")
    expect(opts.localization?.dateFormat).toBe("MM-dd")
    const pf = opts.localization?.priceFormatter as unknown as ((p: number) => string) | undefined
    expect(pf?.(9990)).toBe("NT$9,990")
  })
})

describe("formatChartDate", () => {
  it("string 直接回傳；UTCTimestamp（秒）→ yyyy-mm-dd；BusinessDay → yyyy-mm-dd", () => {
    expect(formatChartDate("2026-08-15")).toBe("2026-08-15")
    expect(formatChartDate(1786752000 as unknown as Time)).toBe("2026-08-15") // 2026-08-15T00:00:00Z 秒
    expect(formatChartDate({ year: 2026, month: 8, day: 15 })).toBe("2026-08-15")
  })
})

describe("computeTooltipPosition", () => {
  it("預設放十字線右上；右側不足改放左側、上方不足改放下方", () => {
    // 右側空間不足 → 改放左側（x - tooltip.width - gap）
    expect(computeTooltipPosition({ x: 590, y: 200 }, { width: 600, height: 360 }, { width: 150, height: 72 })).toEqual({
      left: 428, // 590 - 150 - 12
      top: 116, // 200 - 72 - 12
    })
    // 上方空間不足 → 改放下方（y + gap）
    expect(computeTooltipPosition({ x: 100, y: 20 }, { width: 600, height: 360 }, { width: 150, height: 72 })).toEqual({
      left: 112, // 100 + 12
      top: 32, // 20 + 12
    })
  })

  it("容器極小仍 clamp 至 gap 內不負值", () => {
    const pos = computeTooltipPosition({ x: 0, y: 0 }, { width: 10, height: 10 }, { width: 150, height: 72 })
    expect(pos.left).toBeGreaterThanOrEqual(12)
    expect(pos.top).toBeGreaterThanOrEqual(12)
  })
})
