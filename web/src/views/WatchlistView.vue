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
        name: watchItem.id, // 找不到時顯示 id
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
    <h1>我的追蹤</h1>

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
        <span class="drag-handle" aria-hidden="true">⠿</span>
        <span class="item-name">{{ row.name }}</span>
        <span class="item-price">{{ row.price != null ? formatPrice(row.price) : '—' }}</span>
        <span class="item-diff" :class="diffClass(row.diff)">
          {{ row.diff != null ? formatDiff(row.diff) : '' }}
        </span>
        <Sparkline :points="row.history" />
        <button class="remove-btn" @click="onRemove(row.id)">移除</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.watchlist-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 24px 16px;
}

.watchlist-page h1 {
  font-size: 1.4rem;
  font-weight: 700;
  margin-bottom: 20px;
  color: var(--text);
}

.watchlist-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.watchlist-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--border);
  transition: opacity var(--transition), background-color var(--transition);
}

.watchlist-card:hover {
  background: var(--surface-hover, var(--surface));
}

.watchlist-card.is-gone {
  opacity: 0.5;
}

.drag-handle {
  cursor: grab;
  color: var(--text-dim);
  font-size: 1.1rem;
  user-select: none;
  flex-shrink: 0;
}

.drag-handle:active {
  cursor: grabbing;
}

.item-name {
  flex: 1;
  font-weight: 600;
  font-size: 0.92rem;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.item-price {
  flex-shrink: 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
}

.item-diff {
  flex-shrink: 0;
  font-size: 0.82rem;
  font-weight: 600;
  white-space: nowrap;
  min-width: 64px;
  text-align: right;
}

.price-up {
  color: var(--danger, #e53935);
}

.price-down {
  color: var(--success, #43a047);
}

.price-flat {
  color: var(--text-dim, #999);
}

.remove-btn {
  flex-shrink: 0;
  border: none;
  background: none;
  color: var(--text-dim, #999);
  font-size: 0.82rem;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: color var(--transition), background-color var(--transition);
}

.remove-btn:hover {
  color: var(--danger, #e53935);
  background: var(--danger-soft, rgba(229, 57, 53, 0.08));
}
</style>
