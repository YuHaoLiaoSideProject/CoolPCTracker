// web/src/types/specGroup.ts — 規格分組型別 + 策略配置（開發規格 018 §2.2）
import type { ItemSpec } from "@/types/item"

/** 單一分組選項（Chip 顯示用） */
export interface GroupOption {
  key: string // 分組鍵，如 "DDR5 32GB"；空字串 "" 表示「全部」
  label: string // 顯示文案，與 key 相同
  count: number // 該分組的商品數量
}

/** Per-category 分組策略 */
export interface GroupStrategy {
  fields: (keyof ItemSpec)[]
  /** 分組鍵格式化函式：回傳 string（有效分組）或 null（無規格 → 「其他」） */
  formatKey: (spec: ItemSpec) => string | null
}

/** 「全部」分組的特殊 key */
export const ALL_GROUP_KEY = ""

/** 「其他」分組的特殊 key（無規格商品歸入此組；不顯示在 Chips 中） */
export const OTHER_GROUP_KEY = "__other__"

/** Per-category 分組策略配置 */
export const GROUP_STRATEGY: Record<string, GroupStrategy> = {
  記憶體: {
    fields: ["spec", "ram_gb"],
    formatKey: (s) => {
      const ddr = typeof s.spec === "string" ? s.spec : ""
      const ram = s.ram_gb != null ? `${s.ram_gb}GB` : ""
      const key = `${ddr} ${ram}`.trim()
      return key || null
    },
  },
  記憶卡: {
    fields: ["spec", "capacity"],
    formatKey: (s) => {
      const cardType = typeof s.spec === "string" ? s.spec : ""
      const cap = typeof s.capacity === "string" ? s.capacity : ""
      const key = `${cardType} ${cap}`.trim()
      return key || null
    },
  },
  顯示卡: {
    fields: ["vram_gb", "chip"],
    formatKey: (s) => {
      const vram = s.vram_gb != null ? `${s.vram_gb}GB` : ""
      const chip = s.chip ?? ""
      const key = `${vram} ${chip}`.trim()
      return key || null
    },
  },
  SSD: {
    fields: ["capacity_gb", "interface"],
    formatKey: (s) => {
      const cap = s.capacity_gb != null ? `${s.capacity_gb}GB` : ""
      const iface = s.interface ?? ""
      const key = `${cap} ${iface}`.trim()
      return key || null
    },
  },
  HDD: {
    fields: ["capacity_gb", "rpm"],
    formatKey: (s) => {
      const cap = s.capacity_gb != null ? `${s.capacity_gb}GB` : ""
      const rpm = s.rpm != null ? `${s.rpm}RPM` : ""
      const key = `${cap} ${rpm}`.trim()
      return key || null
    },
  },
  CPU: {
    fields: ["cores", "base_ghz"],
    formatKey: (s) => {
      const cores = s.cores != null ? `${s.cores}核` : ""
      const ghz = s.base_ghz != null ? `${s.base_ghz}GHz` : ""
      const key = `${cores} ${ghz}`.trim()
      return key || null
    },
  },
  主機板: {
    fields: ["socket", "chipset"],
    formatKey: (s) => {
      const socket = s.socket ?? ""
      const chipset = s.chipset ?? ""
      const key = `${socket} ${chipset}`.trim()
      return key || null
    },
  },
  電源: {
    fields: ["wattage_w"],
    formatKey: (s) => {
      return s.wattage_w != null ? `${s.wattage_w}W` : null
    },
  },
}
