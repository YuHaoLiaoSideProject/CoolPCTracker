<script setup lang="ts">
// CompareView.vue — 比價結果頁
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useCompare } from '@/composables/useCompare'
import { useItems } from '@/composables/useItems'
import { buildCompareRows, findCheapestIds, type CompareItem } from '@/utils/compare'
import { MIN_COMPARE } from '@/types/watchlist'

const router = useRouter()
const { selected, count, clear } = useCompare()
const { items: allItems } = useItems()

// 合併邏輯：以 selected 為主，逐筆匹配 useItems 找到對應商品
const compareItems = computed<CompareItem[]>(() => {
  return selected.value.map((sel) => {
    const product = allItems.value.find((item) => item.id === sel.id)
    if (!product) {
      return {
        id: sel.id,
        name: '(找不到)',
        category: sel.category,
        price: null,
        status: 'gone' as const,
        spec: {},
      }
    }
    const lastPrice =
      product.history.length > 0
        ? product.history[product.history.length - 1].p
        : null
    return {
      id: product.id,
      name: product.name,
      category: sel.category,
      price: product.status === 'gone' ? null : lastPrice,
      status: product.status,
      spec: product.spec,
    }
  })
})

const rows = computed(() => buildCompareRows(compareItems.value))
const cheapestIds = computed(() => findCheapestIds(compareItems.value))

// URL 直入防護
const isInvalidSelection = computed(
  () => count.value < MIN_COMPARE || count.value > 6,
)

function onClearCompare() {
  clear()
  router.push('/')
}
</script>

<template>
  <div class="compare-page">
    <h1>比價結果</h1>

    <!-- 無效選取 -->
    <div v-if="isInvalidSelection" class="compare-invalid">
      <p>請至少選擇 2 件商品進行比價</p>
      <router-link to="/" class="back-link">返回列表</router-link>
    </div>

    <!-- 正常比價表 -->
    <template v-else>
      <div class="compare-actions">
        <button class="clear-btn" @click="onClearCompare">清除比價</button>
      </div>
      <div class="compare-scroll">
        <table class="compare-table">
          <thead>
            <tr>
              <th class="row-label"></th>
              <th v-for="item in compareItems" :key="item.id">
                <div class="cell-header">
                  {{ item.name }}
                  <span v-if="cheapestIds.includes(item.id)" class="cheapest-badge">
                    最便宜
                  </span>
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.key">
              <td class="row-label">{{ row.label }}</td>
              <td
                v-for="(val, i) in row.values"
                :key="i"
                :class="{ 'cell-gone': val === null }"
              >
                {{ val ?? '—' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.compare-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px 16px;
}

.compare-page h1 {
  font-size: 1.4rem;
  font-weight: 700;
  margin-bottom: 20px;
  color: var(--text);
}

/* 無效選取 */
.compare-invalid {
  text-align: center;
  padding: 48px 16px;
}

.compare-invalid p {
  font-size: 1rem;
  color: var(--text-dim, #999);
  margin-bottom: 16px;
}

.back-link {
  display: inline-flex;
  align-items: center;
  height: var(--h);
  padding: 0 18px;
  border-radius: var(--radius-sm);
  background: var(--brand);
  color: #fff;
  font-size: 0.86rem;
  font-weight: 600;
  text-decoration: none;
  transition: filter var(--transition);
}

.back-link:hover {
  filter: brightness(1.05);
}

/* 操作列 */
.compare-actions {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.clear-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: var(--h);
  padding: 0 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font-size: 0.86rem;
  font-weight: 600;
  cursor: pointer;
  transition: border-color var(--transition), color var(--transition);
}

.clear-btn:hover {
  border-color: var(--danger, #e53935);
  color: var(--danger, #e53935);
}

/* 比價表滾動容器 */
.compare-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.compare-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}

.compare-table th,
.compare-table td {
  padding: 10px 14px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

.compare-table thead th {
  font-weight: 700;
  color: var(--text);
  background: var(--surface);
  position: sticky;
  top: 0;
}

.cell-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cheapest-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--success-soft, rgba(67, 160, 71, 0.12));
  color: var(--success, #43a047);
  font-size: 0.72rem;
  font-weight: 700;
  width: fit-content;
}

.row-label {
  font-weight: 600;
  color: var(--text-dim, #999);
  min-width: 100px;
}

.cell-gone {
  color: var(--text-dim, #999);
}

@media (max-width: 639px) {
  .compare-table th,
  .compare-table td {
    padding: 8px 10px;
    font-size: 0.82rem;
  }
}
</style>
