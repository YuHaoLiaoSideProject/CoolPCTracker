// web/src/types/item.ts — data/items.json 前端契約（開發規格 003 §2.2）
// 與 crawler/store.py Item + spec_parser 產出對齊；未解析到的欄位為 undefined。

/** 歷史價格點：d = 日期（UTC），p = 台幣整數。
 *  ⚠️ items.json 原始格式為 compact 陣列 ["2026-08-15", 9990]（001 格式決策），
 *  由 useItems.parseItemsFile 於載入層正規化為本物件型別；元件一律使用正規化後型別。 */
export interface PricePoint {
  d: string // "2026-08-15"
  p: number // 9990
}

/** 結構化規格：spec_parser（001）產出；未解析到的欄位為 undefined */
export interface ItemSpec {
  brand?: string
  model?: string
  cores?: number // CPU 核數（篩選條件：CPU核數≥8）
  threads?: number // 執行緒
  base_ghz?: number // 基礎時脈
  turbo_ghz?: number // 超頻時脈
  tdp_w?: number // TDP（瓦）
  socket?: string // 腳位，如 LGA1700
  vram_gb?: number // 顯示卡 VRAM（G）（篩選條件：VRAM≥12G）
  wattage_w?: number // 電源瓦數（篩選條件：瓦數≥750W）
  capacity_gb?: number // 儲存容量（SSD/HDD）
  ram_gb?: number // 記憶體容量
  chip?: string // 顯示卡晶片（如 RTX 4070）
  interface?: string // PCIe 介面
  clock_mhz?: number // 記憶體時脈
  rpm?: number // HDD 轉速
  chipset?: string // 主機板晶片組
  form_factor?: string // 主機板版型
  spec?: string // 輕量分類摘要
  usage?: string // 套裝用途
  summary?: string // 劈發價摘要
  [key: string]: string | number | undefined // 保留擴充欄位
}

export type ItemStatus = "in_stock" | "gone"

export interface Item {
  id: string // hash(主分類 + 正規化名稱)，跨日穩定（001 為 sha256 hex[:16]）
  category: string // 分類**中文標籤**（與 categories.ts label 對齊）：CPU/主機板/…
  subcategory?: string // 子分類標題
  name: string
  spec: ItemSpec // 可能為空物件 {}（無結構化規格）
  flags?: { hot?: boolean; promo?: string; price_drop?: boolean; clearance?: boolean }
  status: ItemStatus
  first_seen: string
  last_seen: string
  history: PricePoint[] // 僅異動時 append；可能為空陣列或僅 1 筆
}

/** data/items.json 頂層契約 */
export interface ItemsFile {
  meta: {
    crawled_at: string // UTC ISO 字串，供過期判定（>7 天，與 007 新鮮度規則共用）
    source: string
    [key: string]: unknown
  }
  items: Item[]
}
