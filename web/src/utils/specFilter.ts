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
export const SPEC_FIELD_LABELS: Record<string, { label: string; unit: string; type: "number" | "string" }> = {
  vram_gb: { label: "VRAM", unit: "G", type: "number" },
  cores: { label: "CPU核數", unit: "核", type: "number" },
  capacity_gb: { label: "容量 GB", unit: "GB", type: "number" },
  chip: { label: "顯示卡晶片", unit: "", type: "string" },
  ram_gb: { label: "記憶體", unit: "GB", type: "number" },
  tdp_w: { label: "TDP", unit: "W", type: "number" },
  // P2：CPU 時脈
  base_ghz: { label: "基礎時脈", unit: "GHz", type: "number" },
  turbo_ghz: { label: "超頻時脈", unit: "GHz", type: "number" },
  // P2：主機板
  chipset: { label: "晶片組", unit: "", type: "string" },
  form_factor: { label: "版型", unit: "", type: "string" },
  // P2：記憶體時脈
  clock_mhz: { label: "記憶體時脈", unit: "MHz", type: "number" },
  // P2：HDD 轉速
  rpm: { label: "轉速", unit: "RPM", type: "number" },
  // P3：SSD
  format: { label: "SSD 格式", unit: "", type: "string" },
  interface: { label: "SSD 介面", unit: "", type: "string" },
}

/** 「VRAM≥12G」→ SpecCondition；格式不符或欄位未知 → null（UI 顯示提示不套用） */
export function parseCondition(input: string): SpecCondition | null {
  // 正規式：標籤 + 可選空白 + ≥/>=/＞/= + 數值 + 可選單位
  // ⚠️ >= 必須置於單字元 > 之前，否則惰性 .+? 會把 「>」吃進標籤（"VRAM >=" → 標籤 "VRAM >"）
  const m = input.trim().match(/^(.+?)\s*(?:>=|≥|＞|=)\s*(\d+(?:\.\d+)?)\s*([A-Za-z\u6838GW]*)$/)
  if (!m) return null
  const label = m[1].trim()
  const entry = Object.entries(SPEC_FIELD_LABELS).find(([, v]) => v.label === label)
  if (!entry) return null
  const [field, meta] = entry
  if (meta.type !== "number") return null // 字串型不走數值解析
  const value = Number(m[2])
  if (!Number.isFinite(value)) return null
  return { id: `${field}-${m[2]}`, label: `${label}≥${m[2]}${m[3] || ""}`, field, type: "number", op: ">=", value, unit: m[3] || "" }
}

/** 字串型條件：顯示卡晶片等值比對 */
export function parseStringCondition(field: SpecField, stringValue: string): SpecCondition | null {
  const meta = SPEC_FIELD_LABELS[field]
  if (!meta || meta.type !== "string") return null
  const trimmed = stringValue.trim()
  if (!trimmed) return null
  return { id: `${field}-${trimmed}`, label: `${meta.label}=${trimmed}`, field, type: "string", op: "=", value: 0, stringValue: trimmed, unit: "" }
}

/** ≥ 語意比對：缺欄位/非數值 → false（靜默排除）；邊界值（等於門檻）→ true */
export function matchesCondition(it: Item, c: SpecCondition): boolean {
  const v = it.spec[c.field]
  if (c.type === "string") {
    if (typeof v !== "string") return false
    return v === c.stringValue
  }
  // 數值型
  if (typeof v !== "number") return false
  return v >= c.value
}

/** 所有可篩選欄位（SpecFilterPanel 下拉選項） */
export const FILTERABLE_FIELDS: { field: SpecField; label: string; unit: string; type: "number" | "string" }[] =
  ([
    "vram_gb", "cores", "capacity_gb", "chip", "ram_gb", "tdp_w",
    // P2：CPU 時脈
    "base_ghz", "turbo_ghz",
    // P2：主機板
    "chipset", "form_factor",
    // P2：記憶體時脈
    "clock_mhz",
    // P2：HDD 轉速
    "rpm",
    // P3：SSD
    "format", "interface",
  ] as SpecField[]).map(f => ({
    field: f,
    label: SPEC_FIELD_LABELS[f].label,
    unit: SPEC_FIELD_LABELS[f].unit,
    type: SPEC_FIELD_LABELS[f].type,
  }))
