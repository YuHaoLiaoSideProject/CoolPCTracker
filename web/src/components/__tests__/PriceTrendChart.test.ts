// web/src/components/__tests__/PriceTrendChart.test.ts — ECharts option 組裝（mock echarts lib）
// jsdom 無 canvas → mock @/lib/echarts，驗證 init/dispose、time 軸、markLine、dataZoom slider、單點降級。
import { describe, expect, it, vi, beforeEach } from "vitest"
import { mount } from "@vue/test-utils"
import { ref } from "vue"
import type { PricePoint } from "@/types/item"

const mocks = vi.hoisted(() => {
  const chart = { setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }
  return { chart, init: vi.fn(() => chart) }
})

vi.mock("@/lib/echarts", () => ({ default: { init: mocks.init } }))

// jsdom 無 ResizeObserver
class ROStub {
  observe = vi.fn()
  disconnect = vi.fn()
  unobserve = vi.fn()
}
vi.stubGlobal("ResizeObserver", ROStub)

import PriceTrendChart from "@/components/PriceTrendChart.vue"

const mk = (pts: [string, number][]): PricePoint[] => pts.map(([d, p]) => ({ d, p }))
const data = (opt: { series: { data: unknown[] }[] }): [string, number][] =>
  opt.series[0].data as [string, number][]
const lastOption = (): any => mocks.chart.setOption.mock.calls.at(-1)?.[0]

beforeEach(() => {
  vi.clearAllMocks()
  // jsdom 的 clientWidth 恆為 0 → stub 成非 0，讓 onMounted init 正常執行（E16 測試另覆寫為 0）
  Object.defineProperty(HTMLElement.prototype, "clientWidth", {
    configurable: true,
    get: () => 480,
  })
})

describe("PriceTrendChart", () => {
  it("init 一次並以 time 軸渲染（E14 非等間距如實呈現）", () => {
    const w = mount(PriceTrendChart, {
      props: { history: mk([["2026-08-13", 9490], ["2026-08-15", 9290]]) },
    })
    expect(mocks.init).toHaveBeenCalledTimes(1)
    const opt = lastOption()
    expect(opt.xAxis.type).toBe("time")
    expect(data(opt)).toEqual([["2026-08-13", 9490], ["2026-08-15", 9290]])
    // 點數 <15 → slider 隱藏、inside 保留
    const zooms = opt.dataZoom as any[]
    expect(zooms[0].type).toBe("inside")
    expect(zooms[1].show).toBe(false)
    w.unmount()
    expect(mocks.chart.dispose).toHaveBeenCalledTimes(1)
  })

  it("點數 ≥15 → dataZoom slider show:true", () => {
    const pts: [string, number][] = []
    for (let i = 0; i < 20; i++) {
      const d = `2026-07-${String(10 + i).padStart(2, "0")}`
      pts.push([d, 5000 + i * 10])
    }
    const w = mount(PriceTrendChart, { props: { history: mk(pts) } })
    const zooms = lastOption().dataZoom as any[]
    expect(zooms[1].show).toBe(true)
    w.unmount()
  })

  it("targetPrice → markLine dashed #f59e0b＋label「目標價 NT$9,500」；無 target → 無 markLine", () => {
    const w = mount(PriceTrendChart, {
      props: { history: mk([["2026-08-13", 10500], ["2026-08-15", 9990]]), targetPrice: 9500 },
    })
    const ml = lastOption().series[0].markLine
    expect(ml).toBeDefined()
    expect(ml.lineStyle).toMatchObject({ type: "dashed", color: "#f59e0b", width: 1.5 })
    expect(ml.silent).toBe(true)
    expect(ml.symbol).toBe("none")
    expect(ml.data).toEqual([{ yAxis: 9500 }])
    expect(ml.label.formatter({ value: 9500 })).toBe("目標價 NT$9,500")
    w.unmount()

    const w2 = mount(PriceTrendChart, {
      props: { history: mk([["2026-08-13", 10500], ["2026-08-15", 9990]]) },
    })
    expect(lastOption().series[0].markLine).toBeUndefined()
    w2.unmount()
  })

  it("yMin/yMax 傳入 yAxis", () => {
    const w = mount(PriceTrendChart, {
      props: { history: mk([["2026-08-13", 10500], ["2026-08-15", 9990]]), yMin: 9790.2, yMax: 11730 },
    })
    expect(lastOption().yAxis.min).toBe(9790.2)
    expect(lastOption().yAxis.max).toBe(11730)
    w.unmount()
  })

  it("單筆降級（E5）：symbolSize 放大、label 顯示價格、無 dataZoom、X 軸以該日為中心", () => {
    const w = mount(PriceTrendChart, { props: { history: mk([["2026-08-15", 5990]]) } })
    const opt = lastOption()
    expect(opt.series[0].symbolSize).toBe(10)
    expect(opt.series[0].label.show).toBe(true)
    expect(opt.series[0].label.formatter({ value: ["2026-08-15", 5990] })).toBe("NT$5,990")
    expect(opt.dataZoom).toEqual([])
    expect(opt.xAxis.min).toBeLessThan(opt.xAxis.max)
    const center = (opt.xAxis.min + opt.xAxis.max) / 2
    expect(center).toBe(new Date("2026-08-15").getTime())
    w.unmount()
  })

  it("props 更新 → notMerge setOption 重新渲染（目標價修改 9500→9800）", async () => {
    const target = ref<number | null>(9500)
    const w = mount(PriceTrendChart, {
      props: { history: mk([["2026-08-13", 10500], ["2026-08-15", 9990]]), targetPrice: target.value },
    })
    expect(mocks.chart.setOption).toHaveBeenCalledTimes(1)
    target.value = 9800
    await w.setProps({ targetPrice: 9800 })
    expect(mocks.chart.setOption).toHaveBeenCalledTimes(2)
    expect(lastOption().series[0].markLine.data).toEqual([{ yAxis: 9800 }])
    w.unmount()
  })

  it("容器 0 寬（E16）：延後 init（init 不執行）", () => {
    const desc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth")
    Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, get: () => 0 })
    try {
      const w = mount(PriceTrendChart, { props: { history: mk([["2026-08-15", 5990]]) } })
      expect(mocks.init).not.toHaveBeenCalled()
      w.unmount()
    } finally {
      if (desc) Object.defineProperty(HTMLElement.prototype, "clientWidth", desc)
    }
  })
})
