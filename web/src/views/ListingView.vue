<script setup lang="ts">
// web/src/views/ListingView.vue — 列表頁組合與 deep link（契約 v2：分類分檔 lazy 載入）
// - 分類狀態唯一真相：useItems.activeCategoryId（index 載入後預設第一個分類）；
//   URL ?category=<id>（"all" = 全部）與之雙向同步。
// - 分類切換 = loadCategory(id)（快取已載入 → 立即切換）；「全部」= loadAll()。
// - 全站搜尋：輸入非空關鍵字 → 切至「全部」並確保全部分類已載入（跨分類搜尋）。
// - 載入/錯誤/空狀態只在列表區域；任何資料失敗不影響側欄／搜尋框渲染。
import { computed, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useItems } from "@/composables/useItems"
import { useFilters } from "@/composables/useFilters"
import { isCategoryKey, labelOf } from "@/data/categories"
import { formatDateTime } from "@/utils/format"
import type { Item } from "@/types/item"
import CategorySidebar from "@/components/CategorySidebar.vue"
import SearchBar from "@/components/SearchBar.vue"
import SpecFilterPanel from "@/components/SpecFilterPanel.vue"
import ProductList from "@/components/ProductList.vue"
import ErrorState from "@/components/ErrorState.vue"

const ALL = "all" // URL ?category=all = 全部視圖

const route = useRoute()
const router = useRouter()
const {
  items, meta, loading, error, retry, isStale,
  categories, activeCategoryId, itemToCategory,
  loadCategory, loadAll,
} = useItems()
const filters = useFilters(items, itemToCategory, activeCategoryId)
// 解構為頂層 binding → 模板中 ref 自動 unwrap（vue-tsc 不 unwrap 巢狀 ref）
const { keyword, conditions, filteredItems, addCondition, removeCondition, clearAll } = filters

// —— URL 參數解析：id 優先；`all` = 全部；舊版 key（?category=GPU）依名稱對照回 id；其餘 → null（預設）——
function resolveParam(v: unknown): string | null | typeof ALL {
  if (v === ALL) return ALL
  if (typeof v === "string" && categories.value.some(c => c.id === v)) return v
  if (isCategoryKey(v)) {
    const c = categories.value.find(c => c.name === labelOf(v))
    if (c) return c.id
  }
  return null
}

/** 套用目前 URL 至資料層（index 目錄就緒後才有效；重複呼叫冪等） */
function applyUrlToState(): void {
  const id = resolveParam(route.query.category)
  if (id === ALL) {
    void loadAll()
  } else if (id) {
    void loadCategory(id)
  } else {
    // 無參數 → 預設第一個分類（useItems bootstrap 已自動載入；此處確保 active 一致）
    const first = categories.value[0]?.id ?? null
    if (first) void loadCategory(first)
  }
}
// index 目錄就緒（categories 更新）時套用 URL（deep link / 直接以分類網址進入）
watch(categories, applyUrlToState, { immediate: true })

// —— URL 與狀態雙向同步：點側欄 → router.replace 更新 URL；URL 變（含前進/後退）→ 更新狀態 ——
function selectCategory(id: string | null) {
  router.replace(id ? { query: { category: id } } : { query: { category: ALL } })
  if (id) void loadCategory(id)
  else void loadAll()
}
watch(
  () => route.query.category,
  () => applyUrlToState(),
)

// —— 全站搜尋：非空關鍵字 → 切至「全部」並 loadAll()（跨分類聚合消費）——
watch(keyword, (k, prev) => {
  if (k.trim() && !prev?.trim()) {
    void loadAll() // 已載入分類快取命中；其餘分類併發抓取
    router.replace({ query: { category: ALL } })
  }
})

// 側欄「全部」總數 = index counts 加總（lazy 下 items 未全載，不能算 items）
const sidebarTotal = computed(() => categories.value.reduce((a, c) => a + c.count, 0))

// 卡片／詳頁需要分類名：itemId → categoryId → category name（v2 外部對照）
const categoryNames = computed<Record<string, string>>(() => {
  const nameById = new Map(categories.value.map(c => [c.id, c.name]))
  const out: Record<string, string> = {}
  for (const [iid, cid] of itemToCategory.value) {
    const n = nameById.get(cid)
    if (n) out[iid] = n
  }
  return out
})

// 目前視圖的「未過濾總數」（分類視圖 = 該分類已載入筆數；全部 = 已載入總數）
const universeTotal = computed(() => {
  if (activeCategoryId.value) {
    let n = 0
    for (const cid of itemToCategory.value.values()) if (cid === activeCategoryId.value) n += 1
    return n
  }
  return items.value.length
})

// —— 004 事件轉接：跳轉詳情頁並回帶分類 context ——
function onOpen(item: Item) {
  router.push({ path: `/product/${encodeURIComponent(item.id)}`, query: route.query })
}

/** 清除全部條件：保留目前分類（BDD #8）；若本來就無搜尋/篩選（空分類的「查看全部商品」）→ 回全部 */
function onClearAll() {
  const wasCategoryEmpty = keyword.value.trim() === "" && conditions.value.length === 0
  clearAll()
  if (wasCategoryEmpty) selectCategory(null)
}

// 錯誤分流：目前視圖「零筆」（無任何已載入命中）且無 loading 時顯示錯誤；有歷史資料 → 舊資料橫幅
const showError = computed(() => !!error.value && !loading.value && filteredItems.value.length === 0)
const showOldData = computed(() => !!error.value && !loading.value && filteredItems.value.length > 0)

// 背景預載詳情頁 chunk（含 lightweight-charts）：首屏不阻塞；首次點進詳情頁免等待下載。
// requestIdleCallback 為主，Safari 無此 API 時 fallback 到 setTimeout。
import { onMounted } from "vue"
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
        :categories="categories"
        :active="activeCategoryId"
        :total="sidebarTotal"
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

      <!-- 載入中：skeleton（側欄/搜尋框仍可見，不白屏；快取切換不觸發） -->
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
          :total="universeTotal"
          :keyword="keyword"
          :conditions="conditions"
          :category-names="categoryNames"
          @clear-all="onClearAll"
          @open="onOpen"
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