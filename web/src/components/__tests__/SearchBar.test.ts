// web/src/components/__tests__/SearchBar.test.ts — 300ms debounce＋外部清空同步
// （開發規格 003 §2.8：受控輸入 + debounce；clearAll 需同步 input 值）
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { mount, flushPromises } from "@vue/test-utils"
import SearchBar from "@/components/SearchBar.vue"

describe("SearchBar", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it("輸入後 300ms 才 emit update:modelValue（debounce）", async () => {
    const w = mount(SearchBar, { props: { modelValue: "" } })
    const input = w.find("input")
    await input.setValue("RTX 4070")
    expect(w.emitted("update:modelValue")).toBeUndefined()

    vi.advanceTimersByTime(300)
    await flushPromises()
    expect(w.emitted("update:modelValue")?.at(-1)).toEqual(["RTX 4070"])
  })

  it("連續輸入只 emit 最後一次（debounce 合併）", async () => {
    const w = mount(SearchBar, { props: { modelValue: "" } })
    const input = w.find("input")
    await input.setValue("R")
    vi.advanceTimersByTime(100)
    await input.setValue("RTX")
    vi.advanceTimersByTime(100)
    await input.setValue("RTX 4070")
    vi.advanceTimersByTime(300)
    await flushPromises()
    expect(w.emitted("update:modelValue")?.length).toBe(1)
    expect(w.emitted("update:modelValue")?.at(-1)).toEqual(["RTX 4070"])
  })

  it("外部清空（props 更新）同步 input 值", async () => {
    const w = mount(SearchBar, { props: { modelValue: "RTX" } })
    await w.setProps({ modelValue: "" }) // clearAll 情境
    expect((w.find("input").element as HTMLInputElement).value).toBe("")
  })

  it("pending debounce 期間外部清空 → 不復活已清除的關鍵字（race fix）", async () => {
    // 真實情境：keyword 已為 "RTX"（已 emit），使用者改輸入 "RTX 4070"（300ms pending），
    // 在 debounce 觸發前按下「清除全部條件」→ 外部 modelValue 由 "RTX" 清空為 ""。
    const w = mount(SearchBar, { props: { modelValue: "RTX" } })
    await w.find("input").setValue("RTX 4070")
    await w.setProps({ modelValue: "" }) // 外部 clearAll（props 有實際變化）
    vi.advanceTimersByTime(300)
    await flushPromises()
    // pending debounce 必須被取消：不得再 emit 舊關鍵字復活（emit "" 為清空同步，屬正常）
    expect(w.emitted("update:modelValue")?.flat()).not.toContain("RTX 4070")
    expect((w.find("input").element as HTMLInputElement).value).toBe("")
  })

  it("點 clear ✕ 按鈕清空並 emit（debounce 後）", async () => {
    const w = mount(SearchBar, { props: { modelValue: "" } })
    await w.find("input").setValue("RTX")
    vi.advanceTimersByTime(300)
    await flushPromises()

    await w.find(".s-clear").trigger("click")
    vi.advanceTimersByTime(300)
    await flushPromises()
    expect((w.find("input").element as HTMLInputElement).value).toBe("")
    expect(w.emitted("update:modelValue")?.at(-1)).toEqual([""])
  })
})
