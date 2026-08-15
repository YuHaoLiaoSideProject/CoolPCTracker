// web/src/components/__tests__/Sparkline.test.ts — 元件測試
// （開發規格 003 §2.10：<2 筆不畫線顯示「—」；≥2 筆渲染 polyline）
import { describe, expect, it } from "vitest"
import { mount } from "@vue/test-utils"
import Sparkline from "@/components/Sparkline.vue"

describe("Sparkline", () => {
  it("少於 2 筆 → 顯示「—」且無 svg", () => {
    const w = mount(Sparkline, { props: { points: [] } })
    expect(w.find("svg").exists()).toBe(false)
    expect(w.find(".sparkline--empty").text()).toBe("—")

    const w2 = mount(Sparkline, { props: { points: [{ d: "2026-08-15", p: 2999 }] } })
    expect(w2.find("svg").exists()).toBe(false)
    expect(w2.find(".sparkline--empty").text()).toBe("—")
  })

  it("≥2 筆 → 渲染 svg + polyline（有座標字串）", () => {
    const w = mount(Sparkline, {
      props: {
        points: [
          { d: "2026-08-13", p: 10000 },
          { d: "2026-08-14", p: 10500 },
          { d: "2026-08-15", p: 10200 },
        ],
      },
    })
    const poly = w.find("polyline")
    expect(poly.exists()).toBe(true)
    expect(poly.attributes("points")).toMatch(/^\d+(\.\d+)?,\d+(\.\d+)? /)
  })
})
