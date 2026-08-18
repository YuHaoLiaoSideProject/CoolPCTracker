// web/src/types/item.ts — 前端資料契約 v2（分類分檔，2026-08-17）
// 契約 v2：api/index.json 的 categories[] 為分類目錄（id/name/file/count）；
// api/items/{file} 為「純陣列」（單一分類 items，每筆**無 category 欄位**——
// 分類是外部狀態：載入哪個檔就知道哪個分類）。Item 型別移除 category。
// 與 crawler/store.py Item + spec_parser 產出對齊；未解析到的欄位為 undefined。

/** 歷史價格點：d = 日期（UTC），p = 台幣整數。
 *  ⚠️ API 原始格式為 compact 陣列 ["2026-08-15", 9990]（001 格式決策），
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
  capacity?: string // 儲存容量（SSD/HDD）：≥1TB 用 TB（如 "2TB"）、<1TB 用 GB（如 "512GB"）
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
  // ⚠️ 契約 v2：**無 category 欄位**（分類為外部狀態，見 CategoryMeta + itemToCategory 對照）
  subcategory?: string // 子分類標題
  name: string
  spec: ItemSpec // 可能為空物件 {}（無結構化規格）
  flags?: { hot?: boolean; promo?: string; price_drop?: boolean; clearance?: boolean }
  status: ItemStatus
  first_seen: string
  last_seen: string
  history: PricePoint[] // 僅異動時 append；可能為空陣列或僅 1 筆
}

/** api/index.json categories[] 單一分類目錄（契約 v2）：
 *  id/name/file/count 均由 index.json 提供（id 與 file 對 crawler 為 G 索引相關，
 *  前端一律視為不透明字串；file 為相對於 api/items/ 的檔名）。 */
export interface CategoryMeta {
  id: string // 不分類負載的不透明 id（URL ?category= 參數值）
  name: string // 分類中文標籤（卡片 chips／詳情麵包屑顯示用）
  file: string // api/items/{file} 檔名（如 "g4.json"）
  count: number // 該分類商品數（側欄顯示；來自 index 當日統計）
  dashboardVisible?: boolean // 是否出現在 Dashboard（true = 顯示在首頁分類 tabs）
}

/** parseItemsFile 輸出容器（舊 001/002 形狀 {meta, items} 亦相容）：
 *  v2 純陣列檔的 meta 由呼叫端注入（index.crawled_at）。 */
export interface ItemsFile {
  meta: { crawled_at: string; source: string }
  items: Item[]
}

/** api/trends/{item_id}.json 契約（O4）：單一商品完整歷史（依 d 升冪、全歷史）。
 *  原始 history 為 compact [d, p] 陣列（001 格式決策），由 useTrend.parseTrendFile
 *  於載入層正規化為 PricePoint[]；元件一律使用正規化後型別。
 *  ⚠️ 分類檔（api/items/）的 history 只剩最近 ≤2 點，完整歷史一律由此檔取得。 */
export interface TrendFile {
  id: string // 與 Item.id 相同（hash(主分類 + 正規化名稱)）
  history: PricePoint[] // 依 d 升冪；可能為空陣列（該商品尚無價格紀錄）
}