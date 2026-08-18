import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/utils/storage', () => ({
  isStorageAvailable: vi.fn(),
  readVersioned: vi.fn(),
  writeVersioned: vi.fn(),
  quarantineCorrupt: vi.fn(),
}))

import {
  isStorageAvailable,
  readVersioned,
  writeVersioned,
  quarantineCorrupt,
} from '@/utils/storage'

const mockIsStorageAvailable = vi.mocked(isStorageAvailable)
const mockReadVersioned = vi.mocked(readVersioned)
const mockWriteVersioned = vi.mocked(writeVersioned)
const mockQuarantineCorrupt = vi.mocked(quarantineCorrupt)

// Reset module singleton between tests
async function importFresh() {
  const { useWatchlist, __resetWatchlistShared } = await import('@/composables/useWatchlist')
  __resetWatchlistShared()
  return { useWatchlist, __resetWatchlistShared }
}

describe('useWatchlist', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    // default: storage available, read returns null (empty)
    mockIsStorageAvailable.mockReturnValue(true)
    mockReadVersioned.mockReturnValue({ ok: true, value: null })
    mockWriteVersioned.mockReturnValue({ ok: true })
  })

  it('1. 新增追蹤成功（items 含新 id，lastPriceSnapshot 正確）', async () => {
    const { useWatchlist } = await importFresh()
    const wl = useWatchlist()

    const result = wl.add('item-aaa', 12990)
    expect(result).toEqual({ ok: true })
    expect(wl.items.value).toHaveLength(1)
    expect(wl.items.value[0].id).toBe('item-aaa')
    expect(wl.items.value[0].lastPriceSnapshot).toBe(12990)
    expect(wl.items.value[0].priceSnapshotAt).toBe(wl.items.value[0].addedAt)
    expect(mockWriteVersioned).toHaveBeenCalledTimes(1)
  })

  it('2. isTracked 正確反映', async () => {
    const { useWatchlist } = await importFresh()
    const wl = useWatchlist()

    expect(wl.isTracked('item-aaa')).toBe(false)
    wl.add('item-aaa', 9990)
    expect(wl.isTracked('item-aaa')).toBe(true)
    expect(wl.isTracked('item-bbb')).toBe(false)
  })

  it('3. 重複加入回傳 already-tracked 且不重複', async () => {
    const { useWatchlist } = await importFresh()
    const wl = useWatchlist()

    wl.add('item-aaa', 9990)
    const result = wl.add('item-aaa', 10990)
    expect(result).toEqual({ ok: false, reason: 'already-tracked' })
    expect(wl.items.value).toHaveLength(1)
    expect(mockWriteVersioned).toHaveBeenCalledTimes(1) // only the first add
  })

  it('4. storage 不可用時回傳 storage-unavailable', async () => {
    mockIsStorageAvailable.mockReturnValue(false)
    const { useWatchlist } = await importFresh()
    const wl = useWatchlist()

    const result = wl.add('item-aaa', 9990)
    expect(result).toEqual({ ok: false, reason: 'storage-unavailable' })
    expect(wl.items.value).toHaveLength(0)
  })

  it('5. quota 超過時回傳 quota-exceeded 且 rollback', async () => {
    mockWriteVersioned.mockReturnValue({
      ok: false,
      error: { kind: 'quota-exceeded', message: 'Storage quota exceeded' },
    })
    const { useWatchlist } = await importFresh()
    const wl = useWatchlist()

    const result = wl.add('item-aaa', 9990)
    expect(result).toEqual({ ok: false, reason: 'quota-exceeded' })
    expect(wl.items.value).toHaveLength(0) // rolled back
  })

  it('6. 移除商品成功', async () => {
    const { useWatchlist } = await importFresh()
    const wl = useWatchlist()

    wl.add('item-aaa', 9990)
    wl.add('item-bbb', 15990)
    expect(wl.items.value).toHaveLength(2)

    wl.remove('item-aaa')
    expect(wl.items.value).toHaveLength(1)
    expect(wl.items.value[0].id).toBe('item-bbb')
    expect(mockWriteVersioned).toHaveBeenCalledTimes(3) // 2 adds + 1 remove
  })

  it('7. 移除不存在的商品不報錯', async () => {
    const { useWatchlist } = await importFresh()
    const wl = useWatchlist()

    expect(() => wl.remove('nonexistent')).not.toThrow()
    expect(wl.items.value).toHaveLength(0)
  })

  it('8. 重新排序後 items 順序正確', async () => {
    const { useWatchlist } = await importFresh()
    const wl = useWatchlist()

    wl.add('item-a', 100)
    wl.add('item-b', 200)
    wl.add('item-c', 300)

    wl.reorder(['item-c', 'item-a', 'item-b'])
    expect(wl.items.value.map(i => i.id)).toEqual(['item-c', 'item-a', 'item-b'])
    expect(mockWriteVersioned).toHaveBeenCalledTimes(4) // 3 adds + 1 reorder
  })

  it('9. updatePriceSnapshot 更新快照', async () => {
    const { useWatchlist } = await importFresh()
    const wl = useWatchlist()

    wl.add('item-aaa', 9990)
    const before = wl.items.value[0].priceSnapshotAt

    // Small delay to ensure different timestamp
    await new Promise(r => setTimeout(r, 10))
    wl.updatePriceSnapshot('item-aaa', 8990)

    expect(wl.items.value[0].lastPriceSnapshot).toBe(8990)
    expect(wl.items.value[0].priceSnapshotAt).not.toBe(before)
    expect(mockWriteVersioned).toHaveBeenCalledTimes(2) // add + update
  })

  it('10. hydrate 讀取已有 localStorage 資料', async () => {
    const existing = {
      version: 1,
      items: [
        {
          id: 'existing-item',
          addedAt: '2026-01-01T00:00:00.000Z',
          lastPriceSnapshot: 5990,
          priceSnapshotAt: '2026-01-01T00:00:00.000Z',
        },
      ],
    }
    mockReadVersioned.mockReturnValue({ ok: true, value: existing })

    const { useWatchlist } = await importFresh()
    const wl = useWatchlist()

    expect(wl.items.value).toHaveLength(1)
    expect(wl.items.value[0].id).toBe('existing-item')
    expect(wl.items.value[0].lastPriceSnapshot).toBe(5990)
  })

  it('11. hydrate 損毀資料時自癒重置', async () => {
    mockReadVersioned.mockReturnValue({
      ok: false,
      error: { kind: 'corrupt', message: 'bad data' },
    })

    const { useWatchlist } = await importFresh()
    const wl = useWatchlist()

    expect(wl.items.value).toHaveLength(0)
    // quarantineCorrupt is called inside readVersioned (real impl), not our code
    // when mocking, we just verify items was reset
  })

  it('12. hydrate 時 storage 不可用設置 error', async () => {
    mockIsStorageAvailable.mockReturnValue(false)

    const { useWatchlist } = await importFresh()
    const wl = useWatchlist()

    expect(wl.error.value).toEqual({
      kind: 'unsupported',
      message: 'localStorage is not available',
    })
    expect(mockReadVersioned).not.toHaveBeenCalled()
  })

  it('13. clearError 清除', async () => {
    mockIsStorageAvailable.mockReturnValue(false)
    const { useWatchlist } = await importFresh()
    const wl = useWatchlist()

    expect(wl.error.value).not.toBeNull()
    wl.clearError()
    expect(wl.error.value).toBeNull()
  })

  it('14. 模組級單例（多處呼叫返回同一 ref）', async () => {
    const { useWatchlist } = await importFresh()
    const wl1 = useWatchlist()
    const wl2 = useWatchlist()

    expect(wl1.items).toBe(wl2.items)
    expect(wl1.error).toBe(wl2.error)
    expect(wl1).toBe(wl2)
  })
})
