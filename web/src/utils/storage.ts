import type { StorageError } from '@/types/watchlist'

// ---------------------------------------------------------------------------
//  Helpers
// ---------------------------------------------------------------------------

function storageArea(area: 'local' | 'session'): Storage | null {
  if (typeof window === 'undefined') return null
  return area === 'local' ? window.localStorage : window.sessionStorage
}

// ---------------------------------------------------------------------------
//  Public API
// ---------------------------------------------------------------------------

/**
 * 探測指定 Storage 是否可用（寫入測試 key 後立即刪除，不污染環境）。
 */
export function isStorageAvailable(area: 'local' | 'session'): boolean {
  const s = storageArea(area)
  if (!s) return false
  try {
    const probe = '__storage_probe__'
    s.setItem(probe, '1')
    s.removeItem(probe)
    return true
  } catch {
    return false
  }
}

/**
 * 版本化讀取。
 * key 組合：`${key}.v${version}`
 * - Storage 不可用 → unsupported
 * - JSON 解析失敗   → corrupt（自動隔離）
 * - 正常           → { ok: true, value }
 */
export function readVersioned<T>(
  area: 'local' | 'session',
  key: string,
  version: number,
): { ok: true; value: T | null } | { ok: false; error: StorageError } {
  const s = storageArea(area)
  if (!s) {
    return { ok: false, error: { kind: 'unsupported', message: 'Storage is not available' } }
  }

  const fullKey = `${key}.v${version}`
  const raw = s.getItem(fullKey)
  if (raw === null) {
    return { ok: true, value: null }
  }

  try {
    const value = JSON.parse(raw) as T
    return { ok: true, value }
  } catch (e) {
    quarantineCorrupt(area, fullKey, raw)
    return {
      ok: false,
      error: { kind: 'corrupt', message: `Failed to parse JSON for key "${fullKey}"` },
    }
  }
}

/**
 * 版本化寫入。
 * - Storage 不可用 → unsupported
 * - QuotaExceeded  → quota-exceeded
 * - 正常           → { ok: true }
 */
export function writeVersioned<T>(
  area: 'local' | 'session',
  key: string,
  version: number,
  value: T,
): { ok: true } | { ok: false; error: StorageError } {
  const s = storageArea(area)
  if (!s) {
    return { ok: false, error: { kind: 'unsupported', message: 'Storage is not available' } }
  }

  const fullKey = `${key}.v${version}`
  try {
    s.setItem(fullKey, JSON.stringify(value))
    return { ok: true }
  } catch (e) {
    if (e instanceof DOMException && e.name === 'QuotaExceededError') {
      return {
        ok: false,
        error: { kind: 'quota-exceeded', message: 'Storage quota exceeded' },
      }
    }
    throw e
  }
}

/**
 * 刪除指定 key。
 */
export function removeKey(area: 'local' | 'session', key: string): void {
  const s = storageArea(area)
  if (!s) return
  s.removeItem(key)
}

/**
 * 將損毀的 raw 資料備份到 `{key}.corrupt-{ts}` 後刪除原 key。
 */
export function quarantineCorrupt(area: 'local' | 'session', key: string, raw: string): void {
  const s = storageArea(area)
  if (!s) return
  const ts = Date.now()
  try {
    s.setItem(`${key}.corrupt-${ts}`, raw)
  } catch {
    // 若空間不足以備份，靜默忽略
  }
  s.removeItem(key)
}
