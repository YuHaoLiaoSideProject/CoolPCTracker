<script setup lang="ts">
// web/src/views/ListingView.vue — 列表頁組合與 deep link（開發規格 003 §2.12）
// 組合全部元件；URL 分類參數為分類狀態的唯一真相來源（雙向同步）；
// 掛載時依 ?category=<key> 初始化（deep link）；載入/錯誤/空狀態只在列表區域。
import { computed, onMounted, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useItems } from "@/composables/useItems"
import { useFilters } from "@/composables/useFilters"
import { isCategoryKey, type CategoryKey } from "@/data/categories"
import { formatDateTime } from "@/utils/format"
import type { Item } from "@/types/item"
import CategorySidebar from "@/components/CategorySidebar.vue"
import SearchBar from "@/components/SearchBar.vue"
import SpecFilterPanel from "@/components/SpecFilterPanel.vue"
import ProductList from "@/components/ProductList.vue"
import ErrorState from "@/components/ErrorState.vue"

const route = useRoute()
const router = useRouter()
const { items, meta, loading, error, retry, isStale } = useItems()
const filters = useFilters(items)
// 解構為頂層 binding → 模板中 ref 自動 unwrap（vue-tsc 不 unwrap 巢狀 ref）
const { keyword, conditions, categoryKey, filteredItems, addCondition, removeCondition, clearAll, setCategory } = filters

// —— deep link：初次進入即依 ?category=<key> 呈現（BDD：直接以分類頁網址進入）——
const initial = route.query.category
if (isCategoryKey(initial)) setCategory(initial as CategoryKey)

// —— URL 與狀態雙向同步：點側欄 → router.replace 更新 URL；URL 變（含前進/後退）→ 更新狀態 ——
function selectCategory(key: CategoryKey | null) {
  router.replace(key ? { query: { category: key } } : { query: {} })
}
watch(
  () => route.query.category,
  v => {
    if (isCategoryKey(v)) setCategory(v as CategoryKey)
    else setCategory(null)
  },
)

// 各分類商品數（側欄顯示）
const counts = computed(() => {
  const map: Record<string, number> = {}
  for (const it of items.value) map[it.category] = (map[it.category] ?? 0) + 1
  return map
})

// —— 004/005 事件轉接：004 已接 /product/:id 路由（onOpen）；
//    005 實作時改接 watchlist/compare store（onToggleWatch / onToggleCompare）——
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function onOpen(item: Item) {
  // 004：跳轉詳情頁並回帶分類 context（?category= 隨 URL 帶至詳情頁，返回列表時保留）
  router.push({ path: `/product/${encodeURIComponent(item.id)}`, query: route.query })
}
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function onToggleWatch(_item: Item) {
  // TODO(005): store.toggle(item.id)
}
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function onToggleCompare(_item: Item) {
  // TODO(005): store.toggle(item.id)
}

/** 清除全部條件：保留目前分類（BDD #8）；若本來就無搜尋/篩選（空分類的「查看全部商品」）→ 回全部 */
function onClearAll() {
  const wasCategoryEmpty = keyword.value.trim() === "" && conditions.value.length === 0
  clearAll()
  if (wasCategoryEmpty) setCategory(null)
}

const showError = computed(() => !!error.value && items.value.length === 0)
const showOldData = computed(() => !!error.value && items.value.length > 0)

// 背景預載詳情頁 chunk（含 echarts）：首屏不阻塞；首次點進詳情頁免等待下載。
// requestIdleCallback 為主，Safari 無此 API 時 fallback 到 setTimeout。
onMounted(() => {
  const prefetch = () => import("@/views/ProductDetailView.vue")
  const ric = (window as any).requestIdleCallback
  if (typeof ric === "function") {
    ric(() => {
      prefetch().catch(() => {})
    }, { timeout: 2000 })
  } else {
    setTimeout(() => {
      prefetch().catch(() => {})
    }, 500)
  }
})
</script>

<template>
  <div class="listing">
    <Transition name="fade">
      <div v-if="isStale" class="stale-banner" role="alert">
        資料可能已過期（最後更新：{{ formatDateTime(meta?.crawled_at) }}）
      </div>
    </Transition>

    <aside class="listing-sidebar">
      <CategorySidebar
        :active="categoryKey as CategoryKey | null"
        :counts="counts"
        @select="selectCategory"
      />
    </aside>

    <main class="listing-main">
      <div class="toolbar">
        <SearchBar v-model="keyword" />
        <SpecFilterPanel
          :conditions="conditions"
          @add="addCondition"
          @remove="removeCondition"
        />
      </div>

      <!-- 載入中：skeleton（側欄/搜尋框仍可見，不白屏） -->
      <div v-if="loading" class="skeleton-list" aria-busy="true">
        <div v-for="n in 6" :key="n" class="sk" />
      </div>

      <!-- 錯誤：僅列表區域顯示 ErrorState + 重試 -->
      <ErrorState v-else-if="showError" :kind="error!" @retry="retry" />

      <!-- 載入成功（或曾有舊資料：錯誤時保留舊資料顯示，§6.1 E2） -->
      <template v-else>
        <div v-if="showOldData" class="stale-banner" role="alert">
          資料載入失敗，目前顯示上次成功載入的資料。
        </div>
        <ProductList
          :items="filteredItems"
          :total="items.length"
          :keyword="keyword"
          :conditions="conditions"
          @clear-all="onClearAll"
          @open="onOpen"
          @toggle-watch="onToggleWatch"
          @toggle-compare="onToggleCompare"
        />
      </template>
    </main>
  </div>
</template>

<style scoped>
.listing {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 20px;
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px;
  align-items: start;
}

.listing-sidebar {
  position: sticky;
  top: 72px;
  align-self: start;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px;
  box-shadow: var(--shadow);
}

.listing-main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.toolbar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 14px;
  box-shadow: var(--shadow);
}

/* skeleton 載入態：灰階漸層閃爍 */
.skeleton-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.skeleton-list .sk {
  height: 120px;
  border-radius: var(--radius);
  background: linear-gradient(90deg, #eee 25%, #f5f5f5 50%, #eee 75%);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
}

@keyframes shimmer {
  to {
    background-position: -200% 0;
  }
}

.stale-banner {
  background: var(--warn-bg);
  border: 1px solid var(--warn-border);
  color: var(--warn-text);
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 0.85rem;
  text-align: center;
  grid-column: 1 / -1;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 平板 640–1023px：側欄收合為頂部水平捲動 chips */
@media (max-width: 1023px) {
  .listing {
    grid-template-columns: 1fr;
  }

  .listing-sidebar {
    position: static;
    padding: 10px 12px;
  }
}

/* 手機 <640px：卡片單欄、chips 換行、價格縱向堆疊 */
@media (max-width: 639px) {
  .listing {
    padding: 10px;
    gap: 12px;
  }

  .toolbar {
    padding: 10px 12px;
  }
}
</style>
