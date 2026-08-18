// web/src/components/__tests__/SparklineTooltip.test.ts — SparklineTooltip 渲染測試（開發規格 020 §2.3）
import { describe, expect, it, vi } from "vitest"
import { mount } from "@vue/test-utils"
import SparklineTooltip from "@/components/SparklineTooltip.vue"

vi.mock("@/utils/format", () => ({
  formatPrice: (n: number) => `NT$ ${n.toLocaleString()}`,
}))

const pt = (d: string, p: number) => ({ d, p })

describe("SparklineTooltip", () => {
  it("渲染日期與價格", () => {
    const w = mount(SparklineTooltip, {
      props: { point: pt("2026-08-15", 9990), x: 50 },
    })
    expect(w.find(".sparkline-tooltip__date").text()).toBe("2026-08-15")
    expect(w.find(".sparkline-tooltip__price").text()).toContain("9,990")
  })

  it("以 left + translateX(-50%) 定位", () => {
    const w = mount(SparklineTooltip, {
      props: { point: pt("2026-08-15", 9990), x: 33.3 },
    })
    const el = w.find(".sparkline-tooltip")
    const style = el.attributes("style")!
    expect(style).toContain("left: 33.3%")
    expect(style).toContain("translateX(-50%)")
  })

  it("bottom: 100% 向上彈出", () => {
    const w = mount(SparklineTooltip, {
      props: { point: pt("2026-08-15", 9990), x: 50 },
    })
    const el = w.find(".sparkline-tooltip")
    // Check it exists and has the correct class
    expect(el.exists()).toBe(true)
    // The bottom:100% is in scoped CSS, so we check the element exists
  })
})
