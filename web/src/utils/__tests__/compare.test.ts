import { describe, it, expect } from 'vitest'
import {
  specColumnsFor,
  buildCompareRows,
  findCheapestIds,
  type CompareItem,
} from '../compare'

// ---------------------------------------------------------------------------
//  specColumnsFor
// ---------------------------------------------------------------------------

describe('specColumnsFor', () => {
  it('returns full CPU columns', () => {
    const cols = specColumnsFor('CPU')
    const keys = cols.map((c) => c.key)
    expect(keys).toEqual([
      'brand', 'model', 'cores', 'threads',
      'base_ghz', 'turbo_ghz', 'tdp_w', 'socket',
    ])
  })

  it('returns GPU columns', () => {
    const cols = specColumnsFor('顯示卡')
    expect(cols.map((c) => c.key)).toEqual([
      'brand', 'model', 'vram_gb', 'chip', 'tdp_w',
    ])
  })

  it('returns RAM columns', () => {
    const cols = specColumnsFor('記憶體')
    expect(cols.map((c) => c.key)).toEqual([
      'brand', 'model', 'ram_gb', 'clock_mhz',
    ])
  })

  it('returns SSD columns', () => {
    const cols = specColumnsFor('SSD')
    expect(cols.map((c) => c.key)).toEqual([
      'brand', 'model', 'capacity', 'interface',
    ])
  })

  it('returns HDD columns including rpm', () => {
    const cols = specColumnsFor('HDD')
    expect(cols.map((c) => c.key)).toEqual([
      'brand', 'model', 'capacity', 'interface', 'rpm',
    ])
  })

  it('returns lightweight columns for 套裝電腦', () => {
    const cols = specColumnsFor('套裝電腦')
    expect(cols.map((c) => c.key)).toEqual(['brand', 'model'])
  })

  it('returns lightweight columns for 準系統', () => {
    const cols = specColumnsFor('準系統')
    expect(cols.map((c) => c.key)).toEqual(['brand', 'model'])
  })

  it('returns lightweight columns for 劈發價組合區', () => {
    const cols = specColumnsFor('劈發價組合區')
    expect(cols.map((c) => c.key)).toEqual(['brand', 'model'])
  })

  it('returns lightweight columns for 記憶卡', () => {
    const cols = specColumnsFor('記憶卡')
    expect(cols.map((c) => c.key)).toEqual(['brand', 'model'])
  })

  it('returns brand+model for unknown categories', () => {
    const cols = specColumnsFor('螢幕')
    expect(cols.map((c) => c.key)).toEqual(['brand', 'model'])
  })
})

// ---------------------------------------------------------------------------
//  buildCompareRows
// ---------------------------------------------------------------------------

function makeItem(overrides: Partial<CompareItem> = {}): CompareItem {
  return {
    id: '1',
    name: 'Test Item',
    category: 'CPU',
    price: 5000,
    status: 'in_stock',
    spec: { brand: 'Intel', model: 'i7-13700K' },
    ...overrides,
  }
}

describe('buildCompareRows', () => {
  it('returns empty array for empty input', () => {
    expect(buildCompareRows([])).toEqual([])
  })

  it('builds price row with NT$ formatting', () => {
    const rows = buildCompareRows([makeItem({ price: 12345 })])
    expect(rows[0]).toEqual({
      key: 'price',
      label: '價格',
      values: ['NT$ 12,345'],
    })
  })

  it('shows "—" for null price (gone item)', () => {
    const rows = buildCompareRows([makeItem({ price: null })])
    expect(rows[0].values).toEqual(['—'])
  })

  it('includes spec columns after price', () => {
    const rows = buildCompareRows([
      makeItem({ spec: { brand: 'Intel', model: 'i7-13700K', cores: 16, threads: 24 } }),
    ])
    const keys = rows.map((r) => r.key)
    expect(keys[0]).toBe('price')
    expect(keys).toContain('brand')
    expect(keys).toContain('cores')
  })

  it('shows "—" for missing spec values', () => {
    const rows = buildCompareRows([
      makeItem({ spec: { brand: 'Intel' } }), // missing model, cores, etc.
    ])
    const modelRow = rows.find((r) => r.key === 'model')
    expect(modelRow).toBeDefined()
    expect(modelRow!.values).toEqual(['—'])
  })

  it('shows "—" for null spec values', () => {
    const rows = buildCompareRows([
      makeItem({ spec: { brand: 'AMD', model: null } }),
    ])
    const modelRow = rows.find((r) => r.key === 'model')
    expect(modelRow!.values).toEqual(['—'])
  })

  it('builds rows for multiple items side-by-side', () => {
    const rows = buildCompareRows([
      makeItem({ id: '1', price: 5000, spec: { brand: 'Intel', model: 'i5' } }),
      makeItem({ id: '2', price: 8000, spec: { brand: 'AMD', model: 'Ryzen 7' } }),
    ])
    expect(rows[0].values).toEqual(['NT$ 5,000', 'NT$ 8,000'])
    expect(rows.find((r) => r.key === 'brand')!.values).toEqual(['Intel', 'AMD'])
  })

  it('uses first item category for columns', () => {
    const rows = buildCompareRows([
      makeItem({ category: '顯示卡', spec: { brand: 'NVIDIA', model: 'RTX 4070', vram_gb: 12 } }),
    ])
    const keys = rows.map((r) => r.key)
    expect(keys).toContain('vram_gb')
    expect(keys).toContain('chip')
  })
})

// ---------------------------------------------------------------------------
//  findCheapestIds
// ---------------------------------------------------------------------------

describe('findCheapestIds', () => {
  it('returns empty array for empty input', () => {
    expect(findCheapestIds([])).toEqual([])
  })

  it('returns single cheapest item id', () => {
    const items: CompareItem[] = [
      makeItem({ id: 'a', price: 3000 }),
      makeItem({ id: 'b', price: 5000 }),
      makeItem({ id: 'c', price: 8000 }),
    ]
    expect(findCheapestIds(items)).toEqual(['a'])
  })

  it('returns all items when all have the same price', () => {
    const items: CompareItem[] = [
      makeItem({ id: 'a', price: 5000 }),
      makeItem({ id: 'b', price: 5000 }),
      makeItem({ id: 'c', price: 5000 }),
    ]
    expect(findCheapestIds(items)).toEqual(['a', 'b', 'c'])
  })

  it('returns multiple ids when tied at lowest price', () => {
    const items: CompareItem[] = [
      makeItem({ id: 'a', price: 3000 }),
      makeItem({ id: 'b', price: 3000 }),
      makeItem({ id: 'c', price: 5000 }),
    ]
    expect(findCheapestIds(items)).toEqual(['a', 'b'])
  })

  it('excludes gone items (price === null)', () => {
    const items: CompareItem[] = [
      makeItem({ id: 'a', price: null }),
      makeItem({ id: 'b', price: 5000 }),
    ]
    expect(findCheapestIds(items)).toEqual(['b'])
  })

  it('returns empty array when all items are gone', () => {
    const items: CompareItem[] = [
      makeItem({ id: 'a', price: null }),
      makeItem({ id: 'b', price: null }),
    ]
    expect(findCheapestIds(items)).toEqual([])
  })

  it('finds cheapest among mixed available and gone items', () => {
    const items: CompareItem[] = [
      makeItem({ id: 'a', price: null }),
      makeItem({ id: 'b', price: 9000 }),
      makeItem({ id: 'c', price: 2000 }),
      makeItem({ id: 'd', price: null }),
    ]
    expect(findCheapestIds(items)).toEqual(['c'])
  })
})
