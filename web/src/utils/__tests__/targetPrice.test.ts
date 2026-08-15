// web/src/utils/__tests__/targetPrice.test.ts — BDD E6 目標價驗證四組訊息＋邊界
import { describe, expect, it } from "vitest"
import { parseTargetPrice } from "@/utils/targetPrice"

describe("parseTargetPrice（BDD Examples 為唯一事實來源）", () => {
  it("空白 → 請輸入目標價（不套用）", () => {
    expect(parseTargetPrice("")).toEqual({ ok: false, error: "請輸入目標價" })
    expect(parseTargetPrice("   ")).toEqual({ ok: false, error: "請輸入目標價" })
  })

  it("非數字 abc → 請輸入有效數字", () => {
    expect(parseTargetPrice("abc")).toEqual({ ok: false, error: "請輸入有效數字" })
    expect(parseTargetPrice("9500元")).toEqual({ ok: false, error: "請輸入有效數字" })
  })

  it("0 與 -100 → 請輸入大於 0 的有效數字", () => {
    expect(parseTargetPrice("0")).toEqual({ ok: false, error: "請輸入大於 0 的有效數字" })
    expect(parseTargetPrice("-100")).toEqual({ ok: false, error: "請輸入大於 0 的有效數字" })
    expect(parseTargetPrice("-5.5")).toEqual({ ok: false, error: "請輸入大於 0 的有效數字" })
  })

  it("有效輸入 → ok（含千分位與小數）", () => {
    expect(parseTargetPrice("9500")).toEqual({ ok: true, value: 9500 })
    expect(parseTargetPrice("9,500")).toEqual({ ok: true, value: 9500 }) // BDD happy path 輸入
    expect(parseTargetPrice(" 9800 ")).toEqual({ ok: true, value: 9800 })
    expect(parseTargetPrice("9500.5")).toEqual({ ok: true, value: 9500.5 })
    expect(parseTargetPrice("0.01")).toEqual({ ok: true, value: 0.01 })
  })
})
