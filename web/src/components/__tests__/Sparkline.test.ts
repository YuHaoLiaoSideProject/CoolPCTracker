// web/src/components/__tests__/Sparkline.test.ts — 元件測試
// （開發規格 003 §2.10：<2 筆不畫線顯示「資料不足」；≥2 筆渲染 polyline）
import { describe, expect, it } from "vitest"
import { mount } from "@vue/test-utils"
import Sparkline from "@/components/Sparkline.vue"

const pt = (d: string, p: number) => ({ d, p })

describe("Sparkline", () => {
  // ── 資料不足：顯示「資料不足」且無 svg ──

  it("空陣列 → 顯示「資料不足」且無 svg", () => {
    const w = mount(Sparkline, { props: { points: [] } })
    expect(w.find("svg").exists()).toBe(false)
    expect(w.find(".sparkline--empty").exists()).toBe(true)
    expect(w.find(".sparkline--empty").text()).toBe("資料不足")
  })

  it("僅 1 筆 → 顯示「資料不足」且無 svg", () => {
    const w = mount(Sparkline, {
      props: { points: [pt("2026-08-15", 2999)] },
    })
    expect(w.find("svg").exists()).toBe(false)
    expect(w.find(".sparkline--empty").exists()).toBe(true)
    expect(w.find(".sparkline--empty").text()).toBe("資料不足")
  })

  // ── 正常渲染：≥2 筆 → svg + polyline ──

  it("2 筆 → 渲染 svg + polyline（2 個座標點）", () => {
    const w = mount(Sparkline, {
      props: {
        points: [pt("2026-08-13", 10000), pt("2026-08-14", 10500)],
      },
    })
    expect(w.find("svg").exists()).toBe(true)
    expect(w.find(".sparkline--empty").exists()).toBe(false)

    const poly = w.find("polyline")
    expect(poly.exists()).toBe(true)
    // 兩個座標點：以空格分隔
    const coords = poly.attributes("points")!.trim().split(/\s+/)
    expect(coords).toHaveLength(2)
    expect(coords[0]).toMatch(/^\d+(\.\d+)?,\d+(\.\d+)?$/)
    expect(coords[1]).toMatch(/^\d+(\.\d+)?,\d+(\.\d+)?$/)
  })

  it("3 筆 → polyline 座標數與輸入筆數一致", () => {
    const w = mount(Sparkline, {
      props: {
        points: [
          pt("2026-08-13", 10000),
          pt("2026-08-14", 10500),
          pt("2026-08-15", 10200),
        ],
      },
    })
    const poly = w.find("polyline")
    expect(poly.exists()).toBe(true)
    const coords = poly.attributes("points")!.trim().split(/\s+/)
    expect(coords).toHaveLength(3)
  })

  it("10 筆 → polyline 座標數為 10（畫全部 points）", () => {
    const points = Array.from({ length: 10 }, (_, i) =>
      pt(`2026-08-${String(i + 1).padStart(2, "0")}`, 8000 + i * 100)
    )
    const w = mount(Sparkline, { props: { points } })
    const poly = w.find("polyline")
    expect(poly.exists()).toBe(true)
    const coords = poly.attributes("points")!.trim().split(/\s+/)
    expect(coords).toHaveLength(10)
  })
})
