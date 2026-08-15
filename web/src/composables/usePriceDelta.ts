// web/src/composables/usePriceDelta.ts — 漲跌計算（開發規格 003 §2.4/§2.10）
// 漲跌基準 = 最後兩筆 history（今日 vs 昨日；history 為「僅異動 append」，
// 故「昨日價」以倒數第二筆為準；僅 1 筆或空 → delta 為 null → 顯示「—」）。
// 漲紅 / 跌綠 / 持平灰；文字（漲/跌/持平/—）與顏色並存（WCAG 1.4.1）。

import { computed } from "vue"
import type { Item, ItemSpec } from "@/types/item"
import { formatNumber } from "@/utils/format"

export function usePriceDelta(item: Item) {
  const lastTwo = item.history.slice(-2)
  const currentPrice = computed(() => lastTwo.at(-1)?.p ?? null)
  const delta = computed(() =>
    lastTwo.length >= 2 ? lastTwo[1].p - lastTwo[0].p : null,
  )
  const deltaClass = computed(() =>
    delta.value == null ? "" : delta.value > 0 ? "price-up" : delta.value < 0 ? "price-down" : "price-flat",
  )
  const deltaText = computed(() => {
    if (delta.value == null) return "—"
    if (delta.value === 0) return "持平"
    const sign = delta.value > 0 ? "漲" : "跌"
    return `${sign} ${formatNumber(Math.abs(delta.value))}`
  })
  return { currentPrice, deltaClass, deltaText }
}

/** 規格 chips 白名單：依分類決定優先欄位（未解析欄位不顯示）。 */
export function specChipTexts(spec: ItemSpec, category: string): string[] {
  const chips: string[] = []
  const push = (label: string, v: string | number | undefined): void => {
    if (v != null && v !== "") chips.push(`${label}${v}`)
  }

  if (category === "CPU") {
    push("", spec.cores != null ? `${spec.cores}核` : undefined)
    push("", spec.threads != null ? `${spec.threads}緒` : undefined)
    push("", spec.base_ghz != null ? `${spec.base_ghz}GHz` : undefined)
    push("", spec.tdp_w != null ? `${spec.tdp_w}W` : undefined)
  } else if (category === "顯示卡") {
    push("", spec.vram_gb != null ? `VRAM ${spec.vram_gb}G` : undefined)
    push("", spec.chip)
    push("", spec.tdp_w != null ? `${spec.tdp_w}W` : undefined)
  } else if (category === "記憶體") {
    push("", spec.capacity_gb != null ? `${spec.capacity_gb}GB` : undefined)
    push("", spec.clock_mhz != null ? `${spec.clock_mhz}MHz` : undefined)
  } else if (category === "SSD" || category === "HDD") {
    push("", spec.capacity_gb != null ? `${spec.capacity_gb}GB` : undefined)
    push("", spec.interface)
    push("", spec.rpm != null ? `${spec.rpm}RPM` : undefined)
  } else if (category === "主機板") {
    push("", spec.socket)
    push("", spec.chipset)
  } else if (category === "記憶卡") {
    push("", spec.capacity_gb != null ? `${spec.capacity_gb}GB` : undefined)
    push("", spec.capacity) // 真資料 spec_parser 產出為字串 token（如 "128GB"）
  } else if (category === "套裝/準系統") {
    push("", spec.brand)
    push("", spec.wattage_w != null ? `${spec.wattage_w}W` : undefined)
    push("", spec.usage)
  } else if (category === "劈發價組合區") {
    push("", spec.brand)
    push("", spec.summary)
  } else {
    push("", spec.brand)
    push("", spec.model)
  }
  return chips
}
