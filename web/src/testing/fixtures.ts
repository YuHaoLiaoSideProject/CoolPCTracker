// web/src/testing/fixtures.ts — 測試共用 fixtures（Item 工廠）
// makeItemsFile 的 items 接受 raw 格式（compact history），
// 由 useItems.parseItemsFile 消費（正規化為 PricePoint）。
import type { Item, ItemsFile } from "@/types/item"

export function makeItem(over: Partial<Item> & { name: string }): Item {
  const { name, ...rest } = over
  return {
    id: `id-${name}`,
    category: "顯示卡",
    spec: {},
    status: "in_stock",
    first_seen: "2026-08-01",
    last_seen: "2026-08-15",
    history: [],
    ...rest,
    name,
  }
}

/** items.json 原始格式（compact history [d, p]；history/spec 可缺） */
export interface RawItem {
  id: string
  category: string
  name: string
  spec?: unknown
  flags?: unknown
  status?: string
  first_seen?: string
  last_seen?: string
  history?: [string, number][]
}

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
