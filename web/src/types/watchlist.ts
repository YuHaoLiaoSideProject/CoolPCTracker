// 追蹤清單與比價的型別定義

export interface WatchlistItem {
  id: string
  name: string                  // 商品名稱（加入時快照）
  addedAt: string               // ISO 8601
  lastPriceSnapshot: number     // 上次查看價格快照（價差基準）
  priceSnapshotAt: string       // ISO 8601
}

export interface WatchlistStorageV1 {
  version: 1
  items: WatchlistItem[]
}

export interface CompareSelectionItem {
  id: string
  category: string
  selectedAt: string            // ISO 8601
}

export interface CompareSelectionStorageV1 {
  version: 1
  items: CompareSelectionItem[]
}

export type StorageErrorKind = 'unsupported' | 'quota-exceeded' | 'corrupt'

export interface StorageError {
  kind: StorageErrorKind
  message: string
}

export const MIN_COMPARE = 2
export const MAX_COMPARE = 6
