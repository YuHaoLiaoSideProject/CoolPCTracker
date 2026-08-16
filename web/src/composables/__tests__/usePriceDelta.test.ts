// web/src/composables/__tests__/usePriceDelta.test.ts — 漲跌三態＋缺昨日價
// （開發規格 003 §2.4 / BDD：漲紅/跌綠/持平灰、僅 1 筆 →「—」）
import { describe, expect, it } from "vitest"
import { usePriceDelta, specChipTexts } from "@/composables/usePriceDelta"
import { makeItem } from "@/testing/fixtures"
import type { PricePoint } from "@/types/item"

function hist(...prices: number[]): PricePoint[] {
  return prices.map((p, i) => ({ d: `2026-08-1${i + 1}`, p }))
}

describe("usePriceDelta", () => {
  it("今日高於昨日 → 漲（price-up + 文字）", () => {
    const item = makeItem({ name: "某 12G 顯示卡", history: hist(10000, 10500) })
    const { currentPrice, deltaClass, deltaText } = usePriceDelta(item)
    expect(currentPrice.value).toBe(10500)
    expect(deltaClass.value).toBe("price-up")
    expect(deltaText.value).toBe("漲 500")
  })

  it("今日低於昨日 → 跌（price-down + 文字）", () => {
    const item = makeItem({ name: "某 8 核 CPU", history: hist(8000, 7500) })
    const { deltaClass, deltaText } = usePriceDelta(item)
    expect(deltaClass.value).toBe("price-down")
    expect(deltaText.value).toBe("跌 500")
  })

  it("持平 → price-flat +「持平」", () => {
    const item = makeItem({ name: "某 750W 套裝主機", history: hist(20000, 20000) })
    const { deltaClass, deltaText } = usePriceDelta(item)
    expect(deltaClass.value).toBe("price-flat")
    expect(deltaText.value).toBe("持平")
  })

  it("多筆 history 取最後兩筆（昨日價 = 倒數第二筆）", () => {
    const item = makeItem({ name: "多筆", history: hist(9000, 9500, 10000) })
    const { currentPrice, deltaText } = usePriceDelta(item)
    expect(currentPrice.value).toBe(10000)
    expect(deltaText.value).toBe("漲 500")
  })

  it("僅 1 筆 history → delta null →「—」且無顏色 class", () => {
    const item = makeItem({ name: "美光 DDR5 32G", history: hist(2999) })
    const { currentPrice, deltaClass, deltaText } = usePriceDelta(item)
    expect(currentPrice.value).toBe(2999)
    expect(deltaClass.value).toBe("")
    expect(deltaText.value).toBe("—")
  })

  it("空 history → currentPrice null +「—」", () => {
    const item = makeItem({ name: "空歷史", history: [] })
    const { currentPrice, deltaClass, deltaText } = usePriceDelta(item)
    expect(currentPrice.value).toBeNull()
    expect(deltaClass.value).toBe("")
    expect(deltaText.value).toBe("—")
  })
})

describe("specChipTexts（規格 chips 依分類白名單）", () => {
  it("CPU：核數/緒/時脈/TDP", () => {
    const chips = specChipTexts({ cores: 14, threads: 20, base_ghz: 3.5, tdp_w: 125 }, "CPU")
    expect(chips).toEqual(["14核", "20緒", "3.5GHz", "125W"])
  })

  it("顯示卡：VRAM/chip/TDP", () => {
    const chips = specChipTexts({ vram_gb: 12, chip: "RTX 4070", tdp_w: 200 }, "顯示卡")
    expect(chips).toEqual(["VRAM 12G", "RTX 4070", "200W"])
  })

  it("記憶體：容量讀 ram_gb（不再讀 capacity_gb，防回歸）", () => {
    const chips = specChipTexts({ ram_gb: 16, clock_mhz: 5600 }, "記憶體")
    expect(chips).toEqual(["16GB", "5600MHz"])
    // 僅有 capacity_gb（儲存容量）的記憶體不應顯示容量 chip
    expect(specChipTexts({ capacity_gb: 32 }, "記憶體")).toEqual([])
  })

  it("SSD/HDD：儲存容量讀 capacity_gb", () => {
    expect(specChipTexts({ capacity_gb: 1024, interface: "M.2" }, "SSD")).toEqual(["1024GB", "M.2"])
    expect(specChipTexts({ capacity_gb: 2048, rpm: 7200 }, "HDD")).toEqual(["2048GB", "7200RPM"])
  })

  it("無規格欄位 → 空陣列（不顯示 chips）", () => {
    expect(specChipTexts({}, "套裝/準系統")).toEqual([])
  })

  it("未解析欄位（undefined）不顯示", () => {
    const chips = specChipTexts({ brand: "技嘉", socket: undefined }, "主機板")
    expect(chips).toEqual([])
  })
})
