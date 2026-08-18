// web/src/components/__tests__/CategoryTabs.test.ts — CategoryTabs 單元測試（019 §2.2）
import { describe, expect, it } from "vitest"
import { mount } from "@vue/test-utils"
import CategoryTabs from "@/components/CategoryTabs.vue"
import type { CategoryMeta } from "@/types/item"

const EMPTY_SET = new Set<string>()

function makeCategories(n: number): CategoryMeta[] {
  return Array.from({ length: n }, (_, i) => ({
    id: `cat${i + 1}`,
    name: `分類${i + 1}`,
    file: `g${i + 1}.json`,
    count: 10 + i,
  }))
}

describe("CategoryTabs", () => {
  it("渲染所有分類 Tab（≤5 個不折疊）", () => {
    const cats = makeCategories(3)
    const w = mount(CategoryTabs, {
      props: { categories: cats, activeId: "cat1", loadingIds: EMPTY_SET },
    })
    const tabs = w.findAll(".cat-tab:not(.cat-tab--toggle)")
    expect(tabs).toHaveLength(3)
    expect(tabs.map((t) => t.text())).toEqual(["分類1", "分類2", "分類3"])
  })

  it("active tab 有 --active class", () => {
    const cats = makeCategories(3)
    const w = mount(CategoryTabs, {
      props: { categories: cats, activeId: "cat2", loadingIds: EMPTY_SET },
    })
    const activeTab = w.find(".cat-tab--active")
    expect(activeTab.exists()).toBe(true)
    expect(activeTab.text()).toContain("分類2")
    expect(activeTab.attributes("aria-pressed")).toBe("true")
  })

  it("activeId 為 null 時無 --active tab", () => {
    const cats = makeCategories(3)
    const w = mount(CategoryTabs, {
      props: { categories: cats, activeId: null, loadingIds: EMPTY_SET },
    })
    expect(w.find(".cat-tab--active").exists()).toBe(false)
  })

  it("點擊 Tab 且 emit select", async () => {
    const cats = makeCategories(3)
    const w = mount(CategoryTabs, {
      props: { categories: cats, activeId: "cat1", loadingIds: EMPTY_SET },
    })
    await w.findAll(".cat-tab:not(.cat-tab--toggle)")[1].trigger("click")
    expect(w.emitted("select")?.[0]).toEqual(["cat2"])
  })

  it("loadingIds 包含 id 時顯示 spinner + --loading class", () => {
    const cats = makeCategories(3)
    const w = mount(CategoryTabs, {
      props: { categories: cats, activeId: "cat1", loadingIds: new Set(["cat2"]) },
    })
    const tab2 = w.findAll(".cat-tab:not(.cat-tab--toggle)")[1]
    expect(tab2.classes()).toContain("cat-tab--loading")
    expect(tab2.find(".cat-tab__spinner").exists()).toBe(true)
    expect(tab2.attributes("aria-busy")).toBe("true")
  })

  it("loadingIds 不含 id 時無 spinner", () => {
    const cats = makeCategories(3)
    const w = mount(CategoryTabs, {
      props: { categories: cats, activeId: "cat1", loadingIds: EMPTY_SET },
    })
    const tabs = w.findAll(".cat-tab:not(.cat-tab--toggle)")
    for (const tab of tabs) {
      expect(tab.find(".cat-tab__spinner").exists()).toBe(false)
    }
  })

  it("≤5 個分類不顯示 toggle 按鈕", () => {
    const cats = makeCategories(5)
    const w = mount(CategoryTabs, {
      props: { categories: cats, activeId: "cat1", loadingIds: EMPTY_SET },
    })
    expect(w.find(".cat-tab--toggle").exists()).toBe(false)
  })

  it("6 個分類顯示「更多 ▼」toggle 按鈕", () => {
    const cats = makeCategories(6)
    const w = mount(CategoryTabs, {
      props: { categories: cats, activeId: "cat1", loadingIds: EMPTY_SET },
    })
    const toggle = w.find(".cat-tab--toggle")
    expect(toggle.exists()).toBe(true)
    expect(toggle.text()).toBe("更多 ▼")
  })

  it("折疊模式只顯示前 5 個 Tab", () => {
    const cats = makeCategories(7)
    const w = mount(CategoryTabs, {
      props: { categories: cats, activeId: "cat1", loadingIds: EMPTY_SET },
    })
    const tabs = w.findAll(".cat-tab:not(.cat-tab--toggle)")
    expect(tabs).toHaveLength(5)
    expect(tabs.map((t) => t.text())).toEqual(["分類1", "分類2", "分類3", "分類4", "分類5"])
  })

  it("點擊「更多 ▼」展開全部 Tab + 顯示「收起 ▲」", async () => {
    const cats = makeCategories(7)
    const w = mount(CategoryTabs, {
      props: { categories: cats, activeId: "cat1", loadingIds: EMPTY_SET },
    })
    await w.find(".cat-tab--toggle").trigger("click")
    const tabs = w.findAll(".cat-tab:not(.cat-tab--toggle)")
    expect(tabs).toHaveLength(7)
    expect(w.find(".cat-tab--toggle").text()).toBe("收起 ▲")
  })

  it("點擊「收起 ▲」重新折疊", async () => {
    const cats = makeCategories(7)
    const w = mount(CategoryTabs, {
      props: { categories: cats, activeId: "cat1", loadingIds: EMPTY_SET },
    })
    // 展開
    await w.find(".cat-tab--toggle").trigger("click")
    expect(w.findAll(".cat-tab:not(.cat-tab--toggle)")).toHaveLength(7)
    // 收起
    await w.find(".cat-tab--toggle").trigger("click")
    expect(w.findAll(".cat-tab:not(.cat-tab--toggle)")).toHaveLength(5)
    expect(w.find(".cat-tab--toggle").text()).toBe("更多 ▼")
  })

  it("9 個分類折疊後顯示前 5 個 + 更多", () => {
    const cats = makeCategories(9)
    const w = mount(CategoryTabs, {
      props: { categories: cats, activeId: "cat1", loadingIds: EMPTY_SET },
    })
    const tabs = w.findAll(".cat-tab:not(.cat-tab--toggle)")
    expect(tabs).toHaveLength(5)
    expect(w.find(".cat-tab--toggle").exists()).toBe(true)
  })

  it("nav 有 aria-label", () => {
    const cats = makeCategories(3)
    const w = mount(CategoryTabs, {
      props: { categories: cats, activeId: "cat1", loadingIds: EMPTY_SET },
    })
    expect(w.find("nav").attributes("aria-label")).toBe("分類切換")
  })
})
