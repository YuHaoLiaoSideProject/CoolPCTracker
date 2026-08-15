// web/src/utils/specFilter.ts — 規格篩選（開發規格 003 §2.6）
// - 條件解析：「VRAM≥12G」→ { field:'vram_gb', op:'>=', value:12, unit:'G' }；僅支援 ≥
// - 比對語意：v >= threshold，**邊界值納入**（12G 命中 12G）
// - 缺欄位商品：item.spec[field] 非 number → 不命中、靜默排除、不報錯
// ⚠️ field 直接使用 item.spec 欄位 key（§2.2 ItemSpec：vram_gb / wattage_w），
//    展示標籤（VRAM / 瓦數）由 SPEC_FIELD_LABELS 對照（規格 §2.6 的 'vram'/'wattage'
//    與 §2.2 契約不一致，此處以行為（BDD 篩選必須命中）為準）。

import type { Item } from "@/types/item"
import type { SpecCondition, SpecField } from "@/types/filters"

/** 顯示標籤 ↔ item.spec 欄位 key 對照（擴充時同步更新此表） */
export const SPEC_FIELD_LABELS: Record<string, { label: string; unit: string }> = {
  vram_gb: { label: "VRAM", unit: "G" },
  cores: { label: "CPU核數", unit: "核" },
  wattage_w: { label: "瓦數", unit: "W" },
  capacity_gb: { label: "容量", unit: "GB" },
  ram_gb: { label: "記憶體", unit: "GB" },
  tdp_w: { label: "TDP", unit: "W" },
}

/** 「VRAM≥12G」→ SpecCondition；格式不符或欄位未知 → null（UI 顯示提示不套用） */
export function parseCondition(input: string): SpecCondition | null {
  // 正規式：標籤 + 可選空白 + ≥/>=/＞/= + 數值 + 可選單位
  // ⚠️ >= 必須置於單字元 > 之前，否則惰性 .+? 會把 「>」吃進標籤（"VRAM >=" → 標籤 "VRAM >"）
  const m = input.trim().match(/^(.+?)\s*(?:>=|≥|＞|=)\s*(\d+(?:\.\d+)?)\s*([A-Za-z\u6838GW]*)$/)
  if (!m) return null
  const label = m[1].trim()
  const field = Object.keys(SPEC_FIELD_LABELS).find(k => SPEC_FIELD_LABELS[k].label === label)
  if (!field) return null
  const value = Number(m[2])
  if (!Number.isFinite(value)) return null
  return { id: `${field}-${m[2]}`, label: `${label}≥${m[2]}${m[3] || ""}`, field, op: ">=", value, unit: m[3] || "" }
}

/** ≥ 語意比對：缺欄位/非數值 → false（靜默排除）；邊界值（等於門檻）→ true */
export function matchesCondition(it: Item, c: SpecCondition): boolean {
  const v = it.spec[c.field]
  if (typeof v !== "number") return false
  return v >= c.value
}

/** 所有可篩選欄位（SpecFilterPanel 下拉選項，P1 三欄位優先置頂） */
export const FILTERABLE_FIELDS: { field: SpecField; label: string; unit: string }[] =
  (["vram_gb", "cores", "wattage_w", "capacity_gb", "ram_gb", "tdp_w"] as SpecField[]).map(f => ({
    field: f,
    label: SPEC_FIELD_LABELS[f].label,
    unit: SPEC_FIELD_LABELS[f].unit,
  }))
