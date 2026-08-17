// web/src/composables/usePriceDelta.ts — 卡片漲跌呈現（開發規格 003 §2.4/§2.10）
// 計算委派 @/lib/priceChange（與 004 詳情頁共用同一事實來源）；此處只做卡片介面。
// 語意：漲跌基準 = history 最後兩筆（「前一日」= 上一筆有紀錄的日期，非日曆昨日）；
// 僅 1 筆 →「新」（price-new 中性色）；空 →「—」；漲紅/跌綠/持平灰（WCAG 1.4.1 文字＋顏色並存）。

import { computed } from "vue"
import type { Item, ItemSpec } from "@/types/item"
import { computePriceChange, priceChangeBadgeClass, priceChangeBadgeText } from "@/lib/priceChange"

export function usePriceDelta(item: Item) {
  const change = computed(() => computePriceChange(item.history))
  const currentPrice = computed(() => change.value.current)
  const deltaClass = computed(() => priceChangeBadgeClass(change.value))
  const deltaText = computed(() => priceChangeBadgeText(change.value))
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
    push("", spec.ram_gb != null ? `${spec.ram_gb}GB` : undefined)
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
