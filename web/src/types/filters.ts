// web/src/types/filters.ts — 篩選條件型別（開發規格 003 §2.5）
// ⚠️ SpecField 直接對應 item.spec 欄位 key（§2.2 ItemSpec 契約：vram_gb / wattage_w），
// 規格 §2.6 的 'vram'/'wattage' 為展示 label；解析層以 SPEC_FIELD_LABELS 對照。

export type SpecField =
  | "vram_gb" | "cores" | "capacity_gb" // P1 篩選條件
  | "chip" // P1 顯示卡晶片（字串型）
  | "ram_gb" // P2：記憶體容量
  | "tdp_w" // P2：TDP
  | "base_ghz" // P2：CPU 基礎時脈
  | "turbo_ghz" // P2：CPU 超頻時脈
  | "chipset" // P2：主機板晶片組（字串型）
  | "form_factor" // P2：主機板版型（字串型）
  | "clock_mhz" // P2：記憶體時脈
  | "rpm" // P2：HDD 轉速
  | "format" // P3：SSD 格式（字串型）
  | "interface" // P3：SSD 介面（字串型）
  | (string & {}) // 保留擴充

export interface SpecCondition {
  id: string // `${field}-${value}`，供 chip 移除
  label: string // 顯示文案，如「VRAM≥12G」
  field: SpecField // 對應 item.spec 欄位
  type: "number" | "string" // 決定比對方式
  op: ">=" | "=" // 數值用 >=，字串用 =（exact match）
  value: number // 數值型門檻
  stringValue?: string // 字串型比對值（chip 等）
  unit: string // 顯示用單位：G / W / 核 …
}

export interface FilterState {
  keyword: string
  conditions: SpecCondition[]
  categoryId: string | null // v2：分類 id（null = 全部；與 useItems.activeCategoryId 一致）
}
