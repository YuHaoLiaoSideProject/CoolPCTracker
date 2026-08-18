import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { isStorageAvailable, readVersioned, writeVersioned, removeKey } from '@/utils/storage'
import { MAX_COMPARE, MIN_COMPARE, type CompareSelectionItem } from '@/types/watchlist'

const STORAGE_KEY = 'coolpc.compare'
const STORAGE_VERSION = 1

// ---------------------------------------------------------------------------
//  Types
// ---------------------------------------------------------------------------

type CompareAddOk = { ok: true }
type CompareAddFail =
  | { ok: false; reason: 'different-category'; message: string }
  | { ok: false; reason: 'max-6'; message: string }
  | { ok: false; reason: 'already-selected' }
  | { ok: false; reason: 'storage-unavailable' }
export type CompareAddResult = CompareAddOk | CompareAddFail

// ---------------------------------------------------------------------------
//  Module-level singleton
// ---------------------------------------------------------------------------

let shared: ReturnType<typeof createCompareState> | null = null

function createCompareState() {
  const selected: Ref<CompareSelectionItem[]> = ref([])

  // ---- hydrate ----
  function hydrate(): void {
    if (!isStorageAvailable('session')) {
      selected.value = []
      return
    }

    const result = readVersioned<{ version: number; items: CompareSelectionItem[] }>(
      'session',
      STORAGE_KEY,
      STORAGE_VERSION,
    )

    if (!result.ok) {
      // corrupt — self-heal
      selected.value = []
      return
    }

    selected.value = result.value?.items ?? []
  }

  // ---- persist ----
  function persist(): boolean {
    if (!isStorageAvailable('session')) return false
    const data: { version: 1; items: CompareSelectionItem[] } = {
      version: STORAGE_VERSION,
      items: selected.value,
    }
    const result = writeVersioned('session', STORAGE_KEY, STORAGE_VERSION, data)
    return result.ok
  }

  // Run hydrate on creation
  hydrate()

  // ---- public API ----

  const category: ComputedRef<string | null> = computed(() => {
    if (selected.value.length === 0) return null
    return selected.value[0].category
  })

  const count: ComputedRef<number> = computed(() => selected.value.length)
  const isFull: ComputedRef<boolean> = computed(() => count.value === MAX_COMPARE)
  const canStart: ComputedRef<boolean> = computed(() => count.value >= MIN_COMPARE)

  function isSelected(id: string): boolean {
    return selected.value.some((item) => item.id === id)
  }

  function add(item: { id: string; category: string }): CompareAddResult {
    if (isSelected(item.id)) {
      return { ok: false, reason: 'already-selected' }
    }

    if (count.value >= MAX_COMPARE) {
      return { ok: false, reason: 'max-6', message: '最多只能比較 6 件商品' }
    }

    if (selected.value.length > 0 && selected.value[0].category !== item.category) {
      return { ok: false, reason: 'different-category', message: '比價僅限同類商品' }
    }

    const newItem: CompareSelectionItem = {
      id: item.id,
      category: item.category,
      selectedAt: new Date().toISOString(),
    }

    const prev = [...selected.value]
    selected.value = [...selected.value, newItem]

    if (!persist()) {
      // rollback
      selected.value = prev
      return { ok: false, reason: 'storage-unavailable' }
    }

    return { ok: true }
  }

  function remove(id: string): void {
    selected.value = selected.value.filter((item) => item.id !== id)
    persist()
  }

  function toggle(item: { id: string; category: string }): CompareAddResult | { ok: true; removed: true } {
    if (isSelected(item.id)) {
      remove(item.id)
      return { ok: true, removed: true }
    }
    return add(item)
  }

  function clear(): void {
    selected.value = []
    if (isStorageAvailable('session')) {
      removeKey('session', STORAGE_KEY)
    }
  }

  return {
    selected,
    category,
    count,
    isFull,
    canStart,
    add,
    remove,
    toggle,
    clear,
    isSelected,
  }
}

// ---------------------------------------------------------------------------
//  Public composable
// ---------------------------------------------------------------------------

/**
 * Reset module-level singleton (for testing).
 */
export function __resetCompareShared(): void {
  shared = null
}

export function useCompare() {
  if (!shared) {
    shared = createCompareState()
  }
  return shared
}
