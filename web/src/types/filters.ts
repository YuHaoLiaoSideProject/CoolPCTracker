// web/src/types/filters.ts — 篩選條件型別（開發規格 003 §2.5）
// ⚠️ SpecField 直接對應 item.spec 欄位 key（§2.2 ItemSpec 契約：vram_gb / wattage_w），
// 規格 §2.6 的 'vram'/'wattage' 為展示 label；解析層以 SPEC_FIELD_LABELS 對照。

export type SpecField =
  | "vram_gb" | "cores" | "wattage_w" // P1 三條件（BDD 需求）
  | "ram_gb" // P2：記憶體容量
  | "tdp_w" // P2：TDP
  | (string & {}) // 保留擴充

export interface SpecCondition {
  id: string // `${field}-${value}`，供 chip 移除
  label: string // 顯示文案，如「VRAM≥12G」
  field: SpecField // 對應 item.spec 欄位
  op: ">=" // 本功能僅支援「大於等於」（tech decision 語意）
  value: number
  unit: string // 顯示用單位：G / W / 核 …
}

export interface FilterState {
  keyword: string
  conditions: SpecCondition[]
  categoryId: string | null // v2：分類 id（null = 全部；與 useItems.activeCategoryId 一致）
}
