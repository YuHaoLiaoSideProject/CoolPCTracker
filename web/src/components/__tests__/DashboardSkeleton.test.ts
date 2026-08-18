// web/src/components/__tests__/DashboardSkeleton.test.ts — DashboardSkeleton 單元測試（017 §2.4）
import { describe, expect, it } from "vitest"
import { mount } from "@vue/test-utils"
import DashboardSkeleton from "@/components/DashboardSkeleton.vue"

describe("DashboardSkeleton", () => {
  it("渲染 5 個 Tab 佔位", () => {
    const w = mount(DashboardSkeleton)
    const tabs = w.findAll(".ds-tab")
    expect(tabs).toHaveLength(5)
  })

  it("渲染 10 個卡片佔位", () => {
    const w = mount(DashboardSkeleton)
    const cards = w.findAll(".ds-card")
    expect(cards).toHaveLength(10)
  })

  it("所有佔位方塊有 shimmer class", () => {
    const w = mount(DashboardSkeleton)
    const tabs = w.findAll(".ds-tab")
    const cards = w.findAll(".ds-card")
    for (const el of [...tabs, ...cards]) {
      expect(el.classes()).toContain("shimmer")
    }
  })

  it("aria-hidden=true（無互動）", () => {
    const w = mount(DashboardSkeleton)
    expect(w.find(".dashboard-skeleton").attributes("aria-hidden")).toBe("true")
  })

  it("包含 Tab 區域與列表區域容器", () => {
    const w = mount(DashboardSkeleton)
    expect(w.find(".ds-tabs").exists()).toBe(true)
    expect(w.find(".ds-list").exists()).toBe(true)
  })
})
