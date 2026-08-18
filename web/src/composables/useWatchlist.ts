import { ref, type Ref } from 'vue'
import {
  isStorageAvailable,
  readVersioned,
  writeVersioned,
  quarantineCorrupt,
} from '@/utils/storage'
import type { WatchlistItem, StorageError, WatchlistStorageV1 } from '@/types/watchlist'

const STORAGE_KEY = 'coolpc.watchlist'
const STORAGE_VERSION = 1

export type AddResult =
  | { ok: true }
  | { ok: false; reason: 'already-tracked' | 'storage-unavailable' | 'quota-exceeded' }

// ---------------------------------------------------------------------------
//  Module-level singleton
// ---------------------------------------------------------------------------

let shared: ReturnType<typeof createWatchlistState> | null = null

function createWatchlistState() {
  const items = ref<WatchlistItem[]>([]) as Ref<WatchlistItem[]>
  const error = ref<StorageError | null>(null) as Ref<StorageError | null>

  // ---- shape validation ----
  function isValidShape(raw: unknown): raw is WatchlistItem {
    if (typeof raw !== 'object' || raw === null) return false
    const r = raw as Record<string, unknown>
    return (
      typeof r.id === 'string' &&
      typeof r.addedAt === 'string' &&
      typeof r.lastPriceSnapshot === 'number' &&
      typeof r.priceSnapshotAt === 'string'
    )
  }

  // ---- hydrate ----
  function hydrate(): void {
    if (!isStorageAvailable('local')) {
      error.value = { kind: 'unsupported', message: 'localStorage is not available' }
      return
    }

    const result = readVersioned<WatchlistStorageV1>('local', STORAGE_KEY, STORAGE_VERSION)
    if (!result.ok) {
      // corrupt — quarantineCorrupt already called inside readVersioned
      items.value = []
      return
    }

    const data = result.value
    if (data === null) {
      items.value = []
      return
    }

    // version check (future migration placeholder)
    if ((data as Record<string, unknown>).version !== STORAGE_VERSION) {
      items.value = []
      return
    }

    //逐筆 shape 驗證
    if (Array.isArray(data.items)) {
      items.value = data.items.filter(isValidShape)
    } else {
      items.value = []
    }
  }

  hydrate()

  // ---- public API ----

  function isTracked(id: string): boolean {
    return items.value.some(item => item.id === id)
  }

  function add(id: string, currentPrice: number): AddResult {
    if (isTracked(id)) {
      return { ok: false, reason: 'already-tracked' }
    }

    if (!isStorageAvailable('local')) {
      return { ok: false, reason: 'storage-unavailable' }
    }

    const now = new Date().toISOString()
    const newItem: WatchlistItem = {
      id,
      addedAt: now,
      lastPriceSnapshot: currentPrice,
      priceSnapshotAt: now,
    }

    // optimistic update
    items.value = [...items.value, newItem]

    const storagePayload: WatchlistStorageV1 = { version: STORAGE_VERSION, items: items.value }
    const result = writeVersioned('local', STORAGE_KEY, STORAGE_VERSION, storagePayload)
    if (!result.ok) {
      // rollback
      items.value = items.value.filter(item => item.id !== id)
      if (result.error.kind === 'quota-exceeded') {
        return { ok: false, reason: 'quota-exceeded' }
      }
      return { ok: false, reason: 'storage-unavailable' }
    }

    return { ok: true }
  }

  function remove(id: string): void {
    const before = items.value
    items.value = items.value.filter(item => item.id !== id)

    const storagePayload: WatchlistStorageV1 = { version: STORAGE_VERSION, items: items.value }
    writeVersioned('local', STORAGE_KEY, STORAGE_VERSION, storagePayload)
    // 失敗不 rollback（移除屬安全方向）
  }

  function reorder(orderedIds: string[]): void {
    const map = new Map(items.value.map(item => [item.id, item]))
    const reordered: WatchlistItem[] = []
    for (const id of orderedIds) {
      const item = map.get(id)
      if (item) reordered.push(item)
    }
    items.value = reordered

    const storagePayload: WatchlistStorageV1 = { version: STORAGE_VERSION, items: items.value }
    writeVersioned('local', STORAGE_KEY, STORAGE_VERSION, storagePayload)
  }

  function updatePriceSnapshot(id: string, price: number): void {
    const idx = items.value.findIndex(item => item.id === id)
    if (idx === -1) return

    const now = new Date().toISOString()
    const updated = [...items.value]
    updated[idx] = { ...updated[idx], lastPriceSnapshot: price, priceSnapshotAt: now }
    items.value = updated

    const storagePayload: WatchlistStorageV1 = { version: STORAGE_VERSION, items: items.value }
    writeVersioned('local', STORAGE_KEY, STORAGE_VERSION, storagePayload)
  }

  function clearError(): void {
    error.value = null
  }

  return {
    items,
    error,
    isTracked,
    add,
    remove,
    reorder,
    updatePriceSnapshot,
    clearError,
  }
}

type WatchlistState = ReturnType<typeof createWatchlistState>

export function useWatchlist(): WatchlistState {
  shared ??= createWatchlistState()
  return shared
}

/** 僅供測試重置單例 */
export function __resetWatchlistShared(): void {
  shared = null
}
