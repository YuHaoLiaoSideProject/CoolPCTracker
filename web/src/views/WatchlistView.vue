<script setup lang="ts">
// WatchlistView.vue — 我的追蹤頁
import { computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useWatchlist } from '@/composables/useWatchlist'
import { useItems } from '@/composables/useItems'
import type { PricePoint } from '@/types/item'
import Sparkline from '@/components/Sparkline.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'

interface WatchRow {
  id: string
  name: string
  price: number | null
  diff: number | null
  history: PricePoint[]
  status: 'in_stock' | 'gone'
}

const router = useRouter()
const { items: watchlistItems, remove, reorder, updatePriceSnapshot } = useWatchlist()
const { items: allItems, loading, error: loadError, retry, loadAll } = useItems()

// 確保全部分類已載入（追蹤的商品可能跨分類）
onMounted(() => {
  loadAll()
})

// 合併邏輯：以 watchlistItems 為主，逐筆匹配 useItems 找到對應商品
const rows = computed<WatchRow[]>(() => {
  return watchlistItems.value.map((watchItem) => {
    const product = allItems.value.find((item) => item.id === watchItem.id)
    if (!product) {
      return {
        id: watchItem.id,
        name: watchItem.name || watchItem.id, // 使用快照名稱，fallback 到 id
        price: null,
        diff: null,
        history: [],
        status: 'gone' as const,
      }
    }
    const isGone = product.status === 'gone'
    if (isGone) {
      return {
        id: product.id,
        name: product.name,
        price: null,
        diff: null,
        history: product.history,
        status: 'gone' as const,
      }
    }
    // in_stock: price = 最末筆 p; diff = price - lastPriceSnapshot
    const lastPrice =
      product.history.length > 0
        ? product.history[product.history.length - 1].p
        : null
    const diff = lastPrice !== null ? lastPrice - watchItem.lastPriceSnapshot : null
    return {
      id: product.id,
      name: product.name,
      price: lastPrice,
      diff,
      history: product.history,
      status: 'in_stock' as const,
    }
  })
})

const isEmpty = computed(() => rows.value.length === 0 && !loading.value)

// 渲染完成後，對每個 in_stock 商品更新快照
watch(
  rows,
  (current) => {
    for (const row of current) {
      if (row.status === 'in_stock' && row.price !== null) {
        updatePriceSnapshot(row.id, row.price)
      }
    }
  },
  { flush: 'post' },
)

// 格式化
function formatPrice(price: number): string {
  return `NT$ ${price.toLocaleString('en-US')}`
}

function formatDiff(diff: number): string {
  const sign = diff > 0 ? '+' : ''
  return `${sign}$${diff.toLocaleString('en-US')}`
}

function diffClass(diff: number | null): string {
  if (diff === null || diff === 0) return 'price-flat'
  return diff > 0 ? 'price-up' : 'price-down'
}

// 拖曳排序
let draggedId: string | null = null

function onDragStart(event: DragEvent, id: string) {
  draggedId = id
  event.dataTransfer!.effectAllowed = 'move'
}

function onDrop(event: DragEvent, targetId: string) {
  event.preventDefault()
  if (!draggedId || draggedId === targetId) return

  const orderedIds = rows.value.map((r) => r.id)
  const fromIdx = orderedIds.indexOf(draggedId)
  const toIdx = orderedIds.indexOf(targetId)
  if (fromIdx === -1 || toIdx === -1) return

  orderedIds.splice(fromIdx, 1)
  orderedIds.splice(toIdx, 0, draggedId)
  reorder(orderedIds)
  draggedId = null
}

function onRemove(id: string) {
  remove(id)
}
</script>

<template>
  <div class="watchlist-page">
    <header class="watchlist-header">
      <h1>我的追蹤</h1>
      <span v-if="rows.length > 0" class="watchlist-count" aria-live="polite">
        {{ rows.length }} 項商品
      </span>
    </header>

    <!-- 載入失敗 -->
    <ErrorState v-if="loadError" :kind="loadError" @retry="retry" />

    <!-- 空狀態 -->
    <EmptyState
      v-else-if="isEmpty"
      kind="category"
      @clear="router.push('/')"
    />

    <!-- 追蹤清單 -->
    <div v-else class="watchlist-list">
      <div
        v-for="row in rows"
        :key="row.id"
        class="watchlist-card"
        :class="{ 'is-gone': row.status === 'gone' }"
        draggable="true"
        @dragstart="onDragStart($event, row.id)"
        @dragover.prevent
        @drop="onDrop($event, row.id)"
      >
        <div class="card-left">
          <span class="drag-handle" aria-hidden="true">⠿</span>
          <div class="card-info">
            <span class="item-name">{{ row.name }}</span>
            <span v-if="row.status === 'gone'" class="gone-badge">已下架</span>
          </div>
        </div>

        <div class="card-right">
          <div class="card-price-group">
            <span class="item-price">{{ row.price != null ? formatPrice(row.price) : '—' }}</span>
            <span class="item-diff" :class="diffClass(row.diff)">
              {{ row.diff != null ? formatDiff(row.diff) : '' }}
            </span>
          </div>
          <Sparkline :points="row.history" class="card-sparkline" />
        </div>

        <button class="remove-btn" @click="onRemove(row.id)" aria-label="移除追蹤">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.watchlist-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px 16px;
}

.watchlist-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 20px;
}

.watchlist-header h1 {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--text);
}

.watchlist-count {
  font-size: 0.85rem;
  color: var(--text-dim);
}

.watchlist-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.watchlist-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  border-radius: var(--radius);
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  overflow: hidden;
  transition: opacity var(--transition), background-color var(--transition), border-color var(--transition);
}

.watchlist-card:hover {
  border-color: var(--brand);
}

.watchlist-card.is-gone {
  opacity: 0.5;
}

.card-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.drag-handle {
  cursor: grab;
  color: var(--text-dim);
  font-size: 1rem;
  user-select: none;
  flex-shrink: 0;
  padding: 4px;
}

.drag-handle:active {
  cursor: grabbing;
}

.card-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.item-name {
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gone-badge {
  display: inline-flex;
  align-items: center;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-dim);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 1px 8px;
  width: fit-content;
}

.card-right {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
  overflow: hidden;
}

.card-price-group {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.item-price {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.item-diff {
  font-size: 0.78rem;
  font-weight: 600;
  white-space: nowrap;
}

.price-up {
  color: var(--price-up);
}

.price-down {
  color: var(--price-down);
}

.price-flat {
  color: var(--price-flat);
}

.card-sparkline {
  flex-shrink: 0;
  width: 80px;
  min-width: 80px;
}

.remove-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: none;
  color: var(--text-dim);
  border-radius: var(--radius-sm);
  transition: color var(--transition), background-color var(--transition);
}

.remove-btn:hover {
  color: var(--danger);
  background: rgba(197, 34, 31, 0.08);
}

.remove-btn:focus-visible {
  outline: var(--focus-ring);
  outline-offset: 1px;
}

@media (max-width: 639px) {
  .watchlist-page {
    padding: 16px 12px;
  }

  .watchlist-card {
    flex-wrap: wrap;
    gap: 12px;
    padding: 12px;
  }

  .card-left {
    flex: 1 1 100%;
  }

  .card-right {
    flex: 1 1 100%;
    justify-content: space-between;
  }

  .card-sparkline {
    display: none;
  }

  .remove-btn {
    position: absolute;
    top: 12px;
    right: 12px;
  }

  .watchlist-card {
    position: relative;
  }
}
</style>
