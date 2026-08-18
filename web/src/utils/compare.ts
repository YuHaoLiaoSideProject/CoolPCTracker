// ---------------------------------------------------------------------------
//  Types
// ---------------------------------------------------------------------------

export interface CompareItem {
  id: string
  name: string
  category: string
  price: number | null          // gone → null
  status: 'in_stock' | 'gone'
  spec: Record<string, string | number | null | undefined>
}

export interface CompareRow {
  key: string
  label: string
  values: Array<string | null>
}

// ---------------------------------------------------------------------------
//  規格欄位定義（依主分類）
// ---------------------------------------------------------------------------

interface SpecColumn {
  key: string
  label: string
}

const SPEC_COLUMNS: Record<string, SpecColumn[]> = {
  CPU: [
    { key: 'brand', label: '品牌' },
    { key: 'model', label: '型號' },
    { key: 'cores', label: '核心數' },
    { key: 'threads', label: '執行緒' },
    { key: 'base_ghz', label: '基礎時脈 (GHz)' },
    { key: 'turbo_ghz', label: '渦輪時脈 (GHz)' },
    { key: 'tdp_w', label: 'TDP (W)' },
    { key: 'socket', label: '腳位' },
  ],
  顯示卡: [
    { key: 'brand', label: '品牌' },
    { key: 'model', label: '型號' },
    { key: 'vram_gb', label: 'VRAM (GB)' },
    { key: 'chip', label: '晶片' },
    { key: 'tdp_w', label: 'TDP (W)' },
  ],
  記憶體: [
    { key: 'brand', label: '品牌' },
    { key: 'model', label: '型號' },
    { key: 'ram_gb', label: '容量 (GB)' },
    { key: 'clock_mhz', label: '時脈 (MHz)' },
  ],
  SSD: [
    { key: 'brand', label: '品牌' },
    { key: 'model', label: '型號' },
    { key: 'capacity', label: '容量' },
    { key: 'interface', label: '介面' },
  ],
  HDD: [
    { key: 'brand', label: '品牌' },
    { key: 'model', label: '型號' },
    { key: 'capacity', label: '容量' },
    { key: 'interface', label: '介面' },
    { key: 'rpm', label: '轉速 (RPM)' },
  ],
}

const LIGHTWEIGHT_CATEGORIES = ['套裝電腦', '準系統', '劈發價組合區', '記憶卡']

/**
 * 依主分類回傳比較表的規格欄位。
 */
export function specColumnsFor(category: string): SpecColumn[] {
  if (SPEC_COLUMNS[category]) {
    return SPEC_COLUMNS[category]
  }
  if (LIGHTWEIGHT_CATEGORIES.includes(category)) {
    return [
      { key: 'brand', label: '品牌' },
      { key: 'model', label: '型號' },
    ]
  }
  // 其他分類
  return [
    { key: 'brand', label: '品牌' },
    { key: 'model', label: '型號' },
  ]
}

// ---------------------------------------------------------------------------
//  比較表建構
// ---------------------------------------------------------------------------

function formatPrice(price: number): string {
  return `NT$ ${price.toLocaleString('en-US')}`
}

/**
 * 建構比較表 rows。
 * 首列為「價格」，後續依 specColumnsFor 回傳的欄位順序。
 * 缺值以 "—" 表示。
 */
export function buildCompareRows(items: CompareItem[]): CompareRow[] {
  if (items.length === 0) return []

  // 取第一個 item 的 category 來決定欄位（比較表只會放同分類的品項）
  const category = items[0].category
  const columns = specColumnsFor(category)

  const rows: CompareRow[] = []

  // 價格列
  rows.push({
    key: 'price',
    label: '價格',
    values: items.map((item) =>
      item.price !== null ? formatPrice(item.price) : '—',
    ),
  })

  // 規格列
  for (const col of columns) {
    rows.push({
      key: col.key,
      label: col.label,
      values: items.map((item) => {
        const val = item.spec[col.key]
        if (val === null || val === undefined) return '—'
        return String(val)
      }),
    })
  }

  return rows
}

// ---------------------------------------------------------------------------
//  最便宜標示
// ---------------------------------------------------------------------------

/**
 * 找出最便宜的 item IDs。排除 gone（price === null）。
 * 同價全部回傳。全部為 gone 或空陣列時回傳空陣列。
 */
export function findCheapestIds(items: CompareItem[]): string[] {
  const candidates = items.filter((i) => i.price !== null)
  if (candidates.length === 0) return []

  const minPrice = Math.min(...candidates.map((i) => i.price as number))
  return candidates
    .filter((i) => i.price === minPrice)
    .map((i) => i.id)
}
