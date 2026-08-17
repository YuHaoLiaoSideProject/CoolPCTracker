// web/src/testing/fixtures.ts — 測試共用 fixtures（Item 工廠）
// v2：Item 型別已無 category（分類為外部狀態）；makeItem 不再帶 category。
// makeItemsFile 的 items 接受 raw 格式（compact history，可含 v1 category 欄位，
// parseItemsFile 會忽略）→ 由 useItems.parseItemsFile 消費（正規化為 PricePoint）。
import type { Item, ItemsFile } from "@/types/item"

export function makeItem(over: Partial<Item> & { name: string }): Item {
  const { name, ...rest } = over
  return {
    id: `id-${name}`,
    spec: {},
    status: "in_stock",
    first_seen: "2026-08-01",
    last_seen: "2026-08-15",
    history: [],
    ...rest,
    name,
  }
}

/** items.json 原始格式（compact history [d, p]；history/spec 可缺）。
 *  category 僅供 v1 舊形狀回溯相容測試（v2 分類檔無此欄位）。 */
export interface RawItem {
  id: string
  category?: string // v1 舊形狀才會有；v2 純陣列檔無（parseItemsFile 忽略）
  name: string
  spec?: unknown
  flags?: unknown
  status?: string
  first_seen?: string
  last_seen?: string
  history?: [string, number][]
}

/** 舊 001/002 形狀容器（{meta, items}；供 parseItemsFile 回溯相容測試） */
export function makeItemsFile(over?: {
  meta?: Partial<ItemsFile["meta"]>
  items?: RawItem[]
}): ItemsFile {
  const defaults: RawItem[] = [
    {
      id: "gpu-4070",
      category: "顯示卡",
      name: "RTX 4070 VENTUS 2X 12G OC",
      spec: { vram_gb: 12, wattage_w: 200 },
      history: [["2026-08-14", 18990]],
    },
    {
      id: "cpu-8core",
      category: "CPU",
      name: "某 8 核 CPU",
      spec: { cores: 8, tdp_w: 65 },
      history: [["2026-08-14", 8000]],
    },
  ]
  return {
    meta: {
      crawled_at: "2026-08-15T06:00:00Z",
      source: "test",
      ...over?.meta,
    },
    items: (over?.items ?? defaults) as unknown as Item[],
  }
}