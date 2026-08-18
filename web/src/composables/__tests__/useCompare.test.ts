import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/utils/storage', () => ({
  isStorageAvailable: vi.fn(),
  readVersioned: vi.fn(),
  writeVersioned: vi.fn(),
  removeKey: vi.fn(),
}))

import {
  isStorageAvailable,
  readVersioned,
  writeVersioned,
  removeKey,
} from '@/utils/storage'

const mockIsStorageAvailable = vi.mocked(isStorageAvailable)
const mockReadVersioned = vi.mocked(readVersioned)
const mockWriteVersioned = vi.mocked(writeVersioned)
const mockRemoveKey = vi.mocked(removeKey)

// Reset module singleton between tests
async function importFresh() {
  const { useCompare, __resetCompareShared } = await import('@/composables/useCompare')
  __resetCompareShared()
  return { useCompare, __resetCompareShared }
}

// Shared test data
const itemA = { id: 'p1', category: 'CPU' }
const itemB = { id: 'p2', category: 'CPU' }
const itemC = { id: 'p3', category: 'GPU' }

describe('useCompare', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    mockIsStorageAvailable.mockReturnValue(true)
    mockReadVersioned.mockReturnValue({ ok: true, value: null })
    mockWriteVersioned.mockReturnValue({ ok: true })
    mockRemoveKey.mockImplementation(() => {})
  })

  // 1. 新增比價選取成功
  it('add: successfully adds an item', async () => {
    const { useCompare } = await importFresh()
    const { add, count, isSelected } = useCompare()

    const result = add(itemA)

    expect(result).toEqual({ ok: true })
    expect(count.value).toBe(1)
    expect(isSelected(itemA.id)).toBe(true)
  })

  // 2. category 計算正確
  it('category: reflects category of first selected item', async () => {
    const { useCompare } = await importFresh()
    const { add, category } = useCompare()

    expect(category.value).toBeNull()

    add(itemA)
    expect(category.value).toBe('CPU')

    add(itemB)
    expect(category.value).toBe('CPU')
  })

  // 3. canStart 至少 2 件才為 true
  it('canStart: true only when count >= MIN_COMPARE (2)', async () => {
    const { useCompare } = await importFresh()
    const { add, canStart } = useCompare()

    expect(canStart.value).toBe(false)

    add(itemA)
    expect(canStart.value).toBe(false)

    add(itemB)
    expect(canStart.value).toBe(true)
  })

  // 4. isFull 達 6 件時為 true
  it('isFull: true only when count === 6', async () => {
    const { useCompare } = await importFresh()
    const { add, isFull } = useCompare()

    expect(isFull.value).toBe(false)

    for (let i = 1; i <= 5; i++) {
      add({ id: `p${i}`, category: 'CPU' })
    }
    expect(isFull.value).toBe(false)

    add({ id: 'p6', category: 'CPU' })
    expect(isFull.value).toBe(true)
  })

  // 5. 跨分類加入被拒絕（different-category）
  it('add: rejects different-category', async () => {
    const { useCompare } = await importFresh()
    const { add, count } = useCompare()

    add(itemA) // CPU
    const result = add(itemC) // GPU

    expect(result).toEqual({
      ok: false,
      reason: 'different-category',
      message: '比價僅限同類商品',
    })
    expect(count.value).toBe(1)
  })

  // 6. 達 6 件上限後再加被拒絕（max-6）
  it('add: rejects when max 6 reached', async () => {
    const { useCompare } = await importFresh()
    const { add, count } = useCompare()

    for (let i = 1; i <= 6; i++) {
      add({ id: `p${i}`, category: 'CPU' })
    }
    expect(count.value).toBe(6)

    const result = add({ id: 'p7', category: 'CPU' })
    expect(result).toEqual({
      ok: false,
      reason: 'max-6',
      message: '最多只能比較 6 件商品',
    })
    expect(count.value).toBe(6)
  })

  // 7. 同分類正常加入（未滿 6 件）
  it('add: allows same-category items under 6', async () => {
    const { useCompare } = await importFresh()
    const { add, count, category } = useCompare()

    const items = Array.from({ length: 5 }, (_, i) => ({
      id: `p${i + 1}`,
      category: 'CPU',
    }))

    for (const item of items) {
      const result = add(item)
      expect(result).toEqual({ ok: true })
    }

    expect(count.value).toBe(5)
    expect(category.value).toBe('CPU')
  })

  // 8. remove 移除選取中的商品
  it('remove: removes selected item', async () => {
    const { useCompare } = await importFresh()
    const { add, remove, count, isSelected } = useCompare()

    add(itemA)
    add(itemB)
    expect(count.value).toBe(2)

    remove(itemA.id)
    expect(count.value).toBe(1)
    expect(isSelected(itemA.id)).toBe(false)
    expect(isSelected(itemB.id)).toBe(true)
  })

  // 9. clear 清空所有選取
  it('clear: empties all selections and calls removeKey', async () => {
    const { useCompare } = await importFresh()
    const { add, clear, count } = useCompare()

    add(itemA)
    add(itemB)
    expect(count.value).toBe(2)

    clear()
    expect(count.value).toBe(0)
    expect(mockRemoveKey).toHaveBeenCalledWith('session', 'coolpc.compare')
  })

  // 10. isSelected 正確反映
  it('isSelected: reflects correct state', async () => {
    const { useCompare } = await importFresh()
    const { add, remove, isSelected } = useCompare()

    expect(isSelected('p1')).toBe(false)

    add(itemA)
    expect(isSelected('p1')).toBe(true)

    remove('p1')
    expect(isSelected('p1')).toBe(false)
  })

  // 11. hydrate 從 sessionStorage 恢復
  it('hydrate: restores items from sessionStorage', async () => {
    const stored = {
      version: 1,
      items: [
        { id: 'p1', category: 'CPU', selectedAt: '2024-01-01T00:00:00.000Z' },
        { id: 'p2', category: 'CPU', selectedAt: '2024-01-02T00:00:00.000Z' },
      ],
    }
    mockReadVersioned.mockReturnValue({ ok: true, value: stored })

    const { useCompare } = await importFresh()
    const { count, isSelected } = useCompare()

    expect(count.value).toBe(2)
    expect(isSelected('p1')).toBe(true)
    expect(isSelected('p2')).toBe(true)
  })

  // 12. hydrate 損毀時自癒
  it('hydrate: self-heals on corrupt data', async () => {
    mockReadVersioned.mockReturnValue({
      ok: false,
      error: { kind: 'corrupt', message: 'bad data' },
    })

    const { useCompare } = await importFresh()
    const { count } = useCompare()

    expect(count.value).toBe(0)
  })

  // 13. storage 不可用時 add 回傳 storage-unavailable
  it('add: returns storage-unavailable when storage is unavailable', async () => {
    mockIsStorageAvailable.mockReturnValue(false)
    mockWriteVersioned.mockReturnValue({
      ok: false,
      error: { kind: 'unsupported', message: 'nope' },
    })

    const { useCompare } = await importFresh()
    const { add, count } = useCompare()

    const result = add(itemA)

    expect(result).toEqual({ ok: false, reason: 'storage-unavailable' })
    expect(count.value).toBe(0)
  })

  // 14. toggle 已選時移除
  it('toggle: removes if already selected', async () => {
    const { useCompare } = await importFresh()
    const { toggle, isSelected, count } = useCompare()

    toggle(itemA)
    expect(isSelected(itemA.id)).toBe(true)
    expect(count.value).toBe(1)

    const result = toggle(itemA)
    expect(result).toEqual({ ok: true, removed: true })
    expect(isSelected(itemA.id)).toBe(false)
    expect(count.value).toBe(0)
  })

  // 15. toggle 未選時加入
  it('toggle: adds if not selected', async () => {
    const { useCompare } = await importFresh()
    const { toggle, isSelected, count } = useCompare()

    const result = toggle(itemA)
    expect(result).toEqual({ ok: true })
    expect(isSelected(itemA.id)).toBe(true)
    expect(count.value).toBe(1)
  })

  // 16. 模組級單例共享 state
  it('singleton: state is shared across calls', async () => {
    const { useCompare } = await importFresh()
    const instance1 = useCompare()
    const instance2 = useCompare()

    instance1.add(itemA)

    // Both instances share the same reactive ref
    expect(instance2.count.value).toBe(1)
    expect(instance2.isSelected(itemA.id)).toBe(true)
  })
})
