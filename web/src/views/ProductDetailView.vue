<script setup lang="ts">
// web/src/views/ProductDetailView.vue — 商品詳情頁（開發規格 004 §2.6，本功能主視圖）
// 路由 /product/:id（hash history）。四態：loading（skeleton）／error（載入失敗＋retry）／
// not-found（找不到商品＋返回列表）／ready（完整版面）。
// 目標價為 session 級 ref：離開路由即銷毀（E12）；驗證訊息以 BDD Examples 為唯一事實來源（E6）。
import { computed, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import SpecTable from "@/components/SpecTable.vue"
import PriceTrendChart from "@/components/PriceTrendChart.vue"
import WatchActions from "@/components/WatchActions.vue"
import ErrorState from "@/components/ErrorState.vue"
import { useItems } from "@/composables/useItems"
import { usePriceHistory, formatTrendLabel } from "@/composables/usePriceHistory"
import { useCrawledAt } from "@/composables/useCrawledAt"
import { parseTargetPrice } from "@/utils/targetPrice"
import { formatPrice } from "@/utils/format"

const route = useRoute()
const router = useRouter()
const { items, meta, loading, error, retry, isStale } = useItems() // 003 契約：共用載入（單例共享，不重複 fetch）

// —— 商品解析（E15：encode/decode 防呆）——
const itemId = computed(() => decodeURIComponent(String(route.params.id)))
const item = computed(() => items.value.find((i) => i.id === itemId.value))
const showError = computed(() => !!error.value)
const notFound = computed(() => !loading.value && !error.value && !item.value)

// —— 價格摘要（§2.4）——
const history = computed(() => item.value?.history ?? [])
const { stats } = usePriceHistory(history)

// —— 最後更新時間（台北時區）與過期判斷（§2.6 / E11，與 003 isStale 同規則）——
const { updatedLabel, isStale: crawledAtStale } = useCrawledAt(computed(() => meta.value?.crawled_at))

// —— 目標價（session 級，E12）——
const targetInput = ref("")
const targetPrice = ref<number | null>(null)
const targetError = ref("") // 非空 → 輸入框紅框＋提示（E6）
const targetOutOfRange = ref(false) // 超出歷史區間提示（E7）

const histMin = computed(() => stats.value.low)
const histMax = computed(() => (history.value.length ? Math.max(...history.value.map((h) => h.p)) : null))

// Y 軸範圍：納入目標價後自動擴展（BDD E7：9,000 超出 9,990~11,500 仍套用且軸 ×0.98/×1.02 擴展）
const yMin = computed(() => Math.min(histMin.value ?? 0, targetPrice.value ?? Infinity) * 0.98)
const yMax = computed(() => Math.max(histMax.value ?? 0, targetPrice.value ?? 0) * 1.02)

function applyTarget(): void {
  const r = parseTargetPrice(targetInput.value)
  if (!r.ok) {
    targetError.value = r.error // 不套用 markLine（E6）
    return
  }
  targetPrice.value = r.value
  targetError.value = ""
  targetOutOfRange.value =
    (histMin.value != null && r.value < histMin.value) ||
    (histMax.value != null && r.value > histMax.value)
}

function clearTarget(): void {
  targetPrice.value = null
  targetInput.value = ""
  targetOutOfRange.value = false
}

// —— 返回列表：保留 003 分類 context（query 回帶，§8 step 8）——
function backToList(): void {
  router.push({ path: "/", query: route.query })
}

// —— 漲跌呈現（E8：金額＋百分比＋方向圖示；僅顏色之外以文字/箭頭傳達，WCAG 1.4.1）——
const trendText = computed(() => {
  if (stats.value.empty) return ""
  if (stats.value.single) return "首日追蹤，尚無漲跌比較"
  if (stats.value.diff == null || stats.value.previous == null) return ""
  return formatTrendLabel(stats.value.diff, stats.value.previous)
})
const trendClass = computed(() =>
  stats.value.trend === "up"
    ? "price-change--up"
    : stats.value.trend === "down"
      ? "price-change--down"
      : "price-change--flat",
)
</script>

<template>
  <div class="detail-page">
    <!-- ── 狀態一：載入中（skeleton，shimmer） ── -->
    <div v-if="loading" class="detail-skeleton" aria-busy="true" aria-label="載入中">
      <div class="sk sk-title" />
      <div class="sk sk-summary" />
      <div class="sk sk-table" />
      <div class="sk sk-chart" />
    </div>

    <!-- ── 狀態二：載入失敗（E1/E2，可重試） ── -->
    <div v-else-if="showError" class="state-center">
      <ErrorState :kind="error!" @retry="retry" />
      <a class="back-link" href="#/" @click.prevent="backToList">← 返回列表</a>
    </div>

    <!-- ── 狀態三：找不到商品（E3/E15） ── -->
    <div v-else-if="notFound" class="state-center">
      <span class="state-ico" aria-hidden="true">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8" />
          <path d="M21 21l-4.35-4.35" />
          <path d="M8 11h6" />
        </svg>
      </span>
      <h2 class="state-title">找不到此商品</h2>
      <p class="state-desc">此商品可能已不存在，或網址中的商品編號有誤。</p>
      <a class="back-link" href="#/" @click.prevent="backToList">← 返回列表</a>
    </div>

    <!-- ── 狀態四：就緒（E4–E14 完整版面） ── -->
    <template v-else-if="item">
      <nav class="detail-breadcrumb" aria-label="麵包屑">
        <a href="#/" @click.prevent="backToList">← 返回列表</a>
        <span class="crumb-sep" aria-hidden="true">/</span>
        <span class="crumb-current">{{ item.category }}</span>
      </nav>

      <h1 class="detail-title">
        <span>{{ item.name }}</span>
        <span v-if="item.status === 'gone'" class="badge-gone">此商品已下架</span>
      </h1>

      <!-- 價格摘要卡 -->
      <section class="price-summary" aria-label="價格摘要">
        <div class="ps-block">
          <span class="ps-label">目前價格</span>
          <span class="price-current">{{ stats.current != null ? formatPrice(stats.current) : "—" }}</span>
        </div>
        <div class="ps-block">
          <span class="ps-label">漲跌</span>
          <span v-if="trendText" class="price-change" :class="trendClass">
            <svg v-if="stats.trend === 'down'" class="trend-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 5v14M19 12l-7 7-7-7" />
            </svg>
            <svg v-else-if="stats.trend === 'up'" class="trend-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
            <span v-else class="trend-ico flat-mark" aria-hidden="true">—</span>
            <span>{{ trendText }}</span>
          </span>
          <span v-else class="ps-na">—</span>
        </div>
        <div class="ps-block">
          <span class="ps-label">歷史最低</span>
          <span v-if="stats.low != null" class="price-low">
            {{ formatPrice(stats.low) }}
            <span class="low-date">（{{ stats.lowDate }}）</span>
          </span>
          <span v-else class="ps-na">—</span>
        </div>
        <div class="ps-block">
          <span class="ps-label">最後更新</span>
          <span class="ps-updated">{{ updatedLabel }}（台北時間）</span>
          <span v-if="crawledAtStale || isStale" class="stale-hint">資料可能已過期</span>
        </div>
      </section>

      <!-- 規格表（E10：空值欄位不渲染） -->
      <section class="detail-section" aria-label="規格">
        <h2 class="section-title">規格</h2>
        <SpecTable :spec="item.spec" />
      </section>

      <!-- 歷史價格趨勢＋目標價 -->
      <section class="detail-section" aria-label="歷史價格趨勢">
        <div class="trend-head">
          <h2 class="section-title">歷史價格趨勢</h2>
          <form class="target-form" @submit.prevent="applyTarget">
            <label class="target-label" for="target-input">目標價</label>
            <input
              id="target-input"
              v-model="targetInput"
              class="target-input"
              :class="{ 'is-error': !!targetError }"
              type="text"
              inputmode="decimal"
              placeholder="如 9,500"
              :aria-invalid="!!targetError"
              aria-describedby="target-error target-hint"
            />
            <button type="submit" class="target-btn">設定目標價</button>
            <button v-if="targetPrice != null" type="button" class="target-btn ghost" @click="clearTarget">清除目標價</button>
          </form>
        </div>
        <p id="target-error" class="target-error" role="alert" aria-live="polite">{{ targetError }}</p>
        <p v-if="targetOutOfRange" id="target-hint" class="hint-out-of-range" role="alert">
          目標價超出歷史區間（已套用，圖表 Y 軸已自動擴展）
        </p>

        <template v-if="stats.empty">
          <p class="no-history">尚無歷史資料</p>
        </template>
        <template v-else>
          <PriceTrendChart
            :history="history"
            :target-price="targetPrice"
            :y-min="yMin"
            :y-max="yMax"
          />
          <p v-if="stats.single" class="chart-note">首日追蹤：僅 1 筆歷史資料，尚無漲跌比較。</p>
        </template>
      </section>

      <!-- 005 預留：追蹤／比價動作區 -->
      <WatchActions :item-id="item.id" />
    </template>
  </div>
</template>

<style scoped>
.detail-page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 24px 16px 64px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── 麵包屑／返回（保留 003 分類 context，query 回帶） ── */
.detail-breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-dim);
}

.detail-breadcrumb a {
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  min-height: var(--h); /* 觸控區 ≥36px（mobile 44px） */
}

.detail-breadcrumb a:hover {
  text-decoration: underline;
}

.crumb-sep {
  color: var(--border);
}

/* ── 標題＋下架 badge（E13） ── */
.detail-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 22px;
  font-weight: 700;
  line-height: 1.4;
}

.badge-gone {
  flex: 0 0 auto;
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fecaca;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 600;
}

/* ── 價格摘要卡 ── */
.price-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  box-shadow: var(--shadow);
}

.ps-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ps-label {
  font-size: 12px;
  color: var(--text-dim);
}

.price-current {
  font-size: 28px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.price-change {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 600;
}

.trend-ico {
  flex: 0 0 auto;
}

.flat-mark {
  font-weight: 700;
}

.price-change--down {
  color: var(--price-down); /* 降價：綠 ▼ */
}

.price-change--up {
  color: var(--price-up); /* 漲價：紅 ▲ */
}

.price-change--flat {
  color: var(--price-flat); /* 持平：灰 — */
}

.price-low {
  font-size: 14px;
  font-weight: 600;
}

.low-date {
  font-size: 13px;
  color: var(--text-dim);
  font-weight: 400;
}

.ps-updated {
  font-size: 13px;
}

.stale-hint {
  font-size: 12px;
  color: var(--warn-text);
  background: var(--warn-bg);
  border: 1px solid var(--warn-border);
  border-radius: 999px;
  padding: 1px 8px;
  align-self: flex-start;
}

.ps-na {
  color: var(--text-dim);
}

/* ── 區塊標題 ── */
.detail-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-title {
  font-size: 16px;
  font-weight: 700;
}

/* ── 趨勢圖標題列＋目標價表單 ── */
.trend-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.target-form {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.target-label {
  font-size: 13px;
  color: var(--text-dim);
}

.target-input {
  width: 160px;
  height: var(--h);
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  transition: border-color var(--transition), box-shadow var(--transition);
}

.target-input:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-soft);
}

.target-input.is-error {
  border-color: var(--danger);
  box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.15);
}

.target-btn {
  height: var(--h);
  padding: 0 16px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--brand);
  color: #fff;
  font-size: 0.85rem;
  font-weight: 600;
  transition: filter var(--transition);
}

.target-btn:hover {
  filter: brightness(1.06);
}

.target-btn.ghost {
  background: var(--surface-2);
  color: var(--text-dim);
  border: 1px solid var(--border);
}

.target-btn.ghost:hover {
  color: var(--text);
}

.target-error {
  color: var(--danger);
  font-size: 13px;
  min-height: 1.2em;
}

.hint-out-of-range {
  color: var(--warn-text);
  background: var(--warn-bg);
  border: 1px solid var(--warn-border);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  font-size: 13px;
}

/* ── 圖表下方小註 ── */
.chart-note {
  font-size: 13px;
  color: var(--text-dim);
}

.no-history {
  padding: 32px 16px;
  text-align: center;
  color: var(--text-dim);
  background: var(--surface);
  border: 1px dashed var(--border);
  border-radius: var(--radius);
  font-size: 14px;
}

/* ── 錯誤／找不到（與 003 共用語義） ── */
.state-center {
  text-align: center;
  padding: 64px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.state-ico {
  color: var(--text-dim);
  margin-bottom: 8px;
}

.state-title {
  font-size: 18px;
  font-weight: 700;
}

.state-desc {
  font-size: 14px;
  color: var(--text-dim);
}

.back-link {
  margin-top: 8px;
  font-size: 14px;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  min-height: var(--h);
}

.back-link:hover {
  text-decoration: underline;
}

/* ── 載入 skeleton（shimmer，與 003 同語義） ── */
.detail-skeleton {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-skeleton .sk {
  border-radius: var(--radius);
  background: linear-gradient(90deg, #eee 25%, #f5f5f5 50%, #eee 75%);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
}

.sk-title {
  height: 28px;
  width: 60%;
}

.sk-summary {
  height: 100px;
}

.sk-table {
  height: 120px;
}

.sk-chart {
  height: 360px;
}

@keyframes shimmer {
  to {
    background-position: -200% 0;
  }
}

/* ── RWD（UIUX §5：mobile 44px 控制高度、摘要單欄） ── */
@media (max-width: 767px) {
  .detail-page {
    padding: 16px 12px 48px;
  }

  .price-summary {
    grid-template-columns: 1fr; /* 單欄堆疊 */
  }

  .target-input {
    height: var(--h-mobile);
    flex: 1;
    min-width: 120px;
  }

  .target-btn {
    height: var(--h-mobile);
    flex: 1;
  }

  .detail-breadcrumb a,
  .back-link {
    min-height: var(--h-mobile);
  }
}
</style>
