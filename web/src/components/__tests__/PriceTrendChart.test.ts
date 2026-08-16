// web/src/components/__tests__/PriceTrendChart.test.ts — lightweight-charts 呼叫參數（mock lwc lib）
// jsdom 無 canvas → mock @/lib/lightweight-charts；驗證 addSeries(LineSeries)/setData/createPriceLine/
// createSeriesMarkers/setVisibleLogicalRange/subscribeCrosshairMove tooltip/雙擊重置/E16 延後 init/onUnmounted 清理。
import { describe, expect, it, vi, beforeEach } from "vitest"
import { mount } from "@vue/test-utils"
import { nextTick, ref } from "vue"
import type { PricePoint } from "@/types/item"

const mocks = vi.hoisted(() => {
  const timeScale = { fitContent: vi.fn<any>(), setVisibleLogicalRange: vi.fn<any>() }
  const series = { setData: vi.fn<any>(), createPriceLine: vi.fn<any>(() => ({})), removePriceLine: vi.fn<any>() }
  const chart = {
    addSeries: vi.fn<any>(() => series),
    applyOptions: vi.fn<any>(),
    subscribeCrosshairMove: vi.fn<any>(),
    subscribeDblClick: vi.fn<any>(),
    unsubscribeCrosshairMove: vi.fn<any>(),
    unsubscribeDblClick: vi.fn<any>(),
    timeScale: vi.fn<any>(() => timeScale),
    remove: vi.fn<any>(),
  }
  const markersApi = { setMarkers: vi.fn<any>(), markers: vi.fn<any>(), detach: vi.fn<any>() }
  return {
    timeScale,
    series,
    chart,
    markersApi,
    createChart: vi.fn<any>(() => chart),
    createSeriesMarkers: vi.fn<any>(() => markersApi),
    // 供未 mock 的 @/lib/priceTrend 使用（真實列舉值）
    LineStyle: { Solid: 0, Dotted: 1, Dashed: 2, LargeDashed: 3, SparseDotted: 4 },
    LineType: { Simple: 0, WithSteps: 1, Curved: 2 },
    ColorType: { Solid: "solid", VerticalGradient: "gradient" },
    CrosshairMode: { Normal: 0, Magnet: 1, Hidden: 2, MagnetOHLC: 3 },
    LineSeries: { type: "Line", isBuiltIn: true, defaultOptions: {} },
    AreaSeries: { type: "Area", isBuiltIn: true, defaultOptions: {} },
  }
})

vi.mock("@/lib/lightweight-charts", () => ({
  createChart: mocks.createChart,
  createSeriesMarkers: mocks.createSeriesMarkers,
  LineStyle: mocks.LineStyle,
  LineType: mocks.LineType,
  ColorType: mocks.ColorType,
  CrosshairMode: mocks.CrosshairMode,
  LineSeries: mocks.LineSeries,
  AreaSeries: mocks.AreaSeries,
}))

// jsdom 無 ResizeObserver
class ROStub {
  observe = vi.fn()
  disconnect = vi.fn()
  unobserve = vi.fn()
}
vi.stubGlobal("ResizeObserver", ROStub)

import PriceTrendChart from "@/components/PriceTrendChart.vue"

const mk = (pts: [string, number][]): PricePoint[] => pts.map(([d, p]) => ({ d, p }))
const seriesDataArg = () => mocks.series.setData.mock.calls.at(-1)?.[0] as { time: string; value: number }[]
const priceLineArg = () => mocks.series.createPriceLine.mock.calls.at(-1)?.[0] as { price: number }
const markersArg = () => mocks.createSeriesMarkers.mock.calls.at(-1)?.[1] as unknown[]
const crosshairHandler = () => mocks.chart.subscribeCrosshairMove.mock.calls[0]?.[0] as (p: unknown) => void
const dblClickHandler = () => mocks.chart.subscribeDblClick.mock.calls[0]?.[0] as () => void

beforeEach(() => {
  vi.clearAllMocks()
  // jsdom 的 clientWidth 恆為 0 → stub 成非 0，讓 onMounted init 正常執行（E16 測試另覆寫為 0）
  Object.defineProperty(HTMLElement.prototype, "clientWidth", {
    configurable: true,
    get: () => 480,
  })
})

describe("PriceTrendChart", () => {
  it("init：createChart → addSeries(LineSeries) → setData({time,value}) → createSeriesMarkers → 訂閱", () => {
    const w = mount(PriceTrendChart, {
      props: { history: mk([["2026-08-13", 9490], ["2026-08-15", 9290]]) },
    })
    expect(mocks.createChart).toHaveBeenCalledTimes(1)
    expect(mocks.chart.addSeries).toHaveBeenCalledWith(
      mocks.LineSeries,
      expect.objectContaining({ color: "#1f6feb", lineWidth: 2, priceLineVisible: false, lastValueVisible: false }),
    )
    expect(seriesDataArg()).toEqual([
      { time: "2026-08-13", value: 9490 },
      { time: "2026-08-15", value: 9290 },
    ])
    expect(mocks.createSeriesMarkers).toHaveBeenCalledWith(mocks.series, expect.any(Array))
    expect(mocks.chart.subscribeCrosshairMove).toHaveBeenCalledTimes(1)
    expect(mocks.chart.subscribeDblClick).toHaveBeenCalledTimes(1)
    w.unmount()
    expect(mocks.chart.remove).toHaveBeenCalledTimes(1)
  })

  it("≤24 點 → markers 每點一個；>24 點 → markers 空", () => {
    const w2 = mount(PriceTrendChart, {
      props: { history: mk([["2026-08-13", 9490], ["2026-08-15", 9290]]) },
    })
    expect(markersArg()).toHaveLength(2)
    w2.unmount()

    const pts: [string, number][] = Array.from({ length: 25 }, (_, i) => [
      `2026-07-${String(1 + i).padStart(2, "0")}`,
      5000 + i,
    ])
    const w25 = mount(PriceTrendChart, { props: { history: mk(pts) } })
    expect(markersArg()).toHaveLength(0)
    w25.unmount()
  })

  it("targetPrice → createPriceLine（dashed #f59e0b、title 目標價）；無 target → 不建立", () => {
    const w = mount(PriceTrendChart, {
      props: { history: mk([["2026-08-13", 10500], ["2026-08-15", 9990]]), targetPrice: 9500 },
    })
    expect(mocks.series.createPriceLine).toHaveBeenCalledTimes(1)
    expect(priceLineArg()).toEqual({
      price: 9500,
      color: "#f59e0b",
      lineStyle: 2, // LineStyle.Dashed
      lineWidth: 2,
      title: "目標價",
      axisLabelVisible: true,
    })
    w.unmount()

    vi.clearAllMocks()
    const w2 = mount(PriceTrendChart, {
      props: { history: mk([["2026-08-13", 10500], ["2026-08-15", 9990]]) },
    })
    expect(mocks.series.createPriceLine).not.toHaveBeenCalled()
    w2.unmount()
  })

  it("單筆降級（E5）：marker 附價格文字、setVisibleLogicalRange 居中", () => {
    const w = mount(PriceTrendChart, { props: { history: mk([["2026-08-15", 5990]]) } })
    const markers = markersArg() as { text?: string }[]
    expect(markers).toHaveLength(1)
    expect(markers[0].text).toBe("NT$5,990")
    expect(mocks.timeScale.setVisibleLogicalRange).toHaveBeenCalledWith({ from: -1.5, to: 1.5 })
    w.unmount()
  })

  it("crosshair move → 自寫 tooltip（日期＋價格＋目標價）；離開 → 隱藏", async () => {
    const w = mount(PriceTrendChart, {
      props: { history: mk([["2026-08-13", 10500], ["2026-08-15", 9990]]), targetPrice: 9500 },
    })
    crosshairHandler()({
      point: { x: 100, y: 200 },
      time: "2026-08-15",
      seriesData: new Map([[mocks.series, { time: "2026-08-15", value: 9990 }]]),
    })
    await nextTick()
    expect(w.find(".chart-tooltip").exists()).toBe(true)
    expect(w.find(".tt-date").text()).toBe("2026-08-15")
    expect(w.find(".tt-price").text()).toBe("價格：NT$9,990")
    expect(w.find(".tt-target").text()).toBe("目標價 NT$9,500")

    crosshairHandler()({ point: undefined, time: undefined, seriesData: new Map() })
    await nextTick()
    expect(w.find(".chart-tooltip").exists()).toBe(false)
    w.unmount()
  })

  it("雙擊 → timeScale().fitContent()（重置縮放）", () => {
    const w = mount(PriceTrendChart, {
      props: { history: mk([["2026-08-13", 10500], ["2026-08-15", 9990]]) },
    })
    dblClickHandler()()
    expect(mocks.timeScale.fitContent).toHaveBeenCalledTimes(1)
    w.unmount()
  })

  it("props 更新（目標價 9500→9800）→ 重建 price line 並重設資料", async () => {
    const target = ref<number | null>(9500)
    const w = mount(PriceTrendChart, {
      props: { history: mk([["2026-08-13", 10500], ["2026-08-15", 9990]]), targetPrice: target.value },
    })
    expect(mocks.series.setData).toHaveBeenCalledTimes(1)
    expect(priceLineArg().price).toBe(9500)
    target.value = 9800
    await w.setProps({ targetPrice: 9800 })
    expect(mocks.series.setData).toHaveBeenCalledTimes(2)
    expect(mocks.series.removePriceLine).toHaveBeenCalledTimes(1)
    expect(priceLineArg().price).toBe(9800)
    w.unmount()
  })

  it("容器 0 寬（E16）：延後 init（createChart 不執行）", () => {
    const desc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth")
    Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, get: () => 0 })
    try {
      const w = mount(PriceTrendChart, { props: { history: mk([["2026-08-15", 5990]]) } })
      expect(mocks.createChart).not.toHaveBeenCalled()
      w.unmount()
    } finally {
      if (desc) Object.defineProperty(HTMLElement.prototype, "clientWidth", desc)
    }
  })

  it("onUnmounted：取消訂閱＋detach markers＋remove chart＋disconnect observer", () => {
    const w = mount(PriceTrendChart, { props: { history: mk([["2026-08-15", 5990]]) } })
    w.unmount()
    expect(mocks.chart.unsubscribeCrosshairMove).toHaveBeenCalledTimes(1)
    expect(mocks.chart.unsubscribeDblClick).toHaveBeenCalledTimes(1)
    expect(mocks.markersApi.detach).toHaveBeenCalledTimes(1)
    expect(mocks.chart.remove).toHaveBeenCalledTimes(1)
  })
})
