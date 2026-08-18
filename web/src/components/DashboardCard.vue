<!-- web/src/components/DashboardCard.vue — 精簡版商品卡片（開發規格 017 §2.3）-->
<!-- 顯示：名稱、目前價格、歷史最低價、🥇、規格 Chips、已下架標籤。點擊導航至詳情頁。-->
<script setup lang="ts">
import { computed } from "vue"
import { useRouter } from "vue-router"
import type { Item } from "@/types/item"
import { usePriceDelta, specChipTexts } from "@/composables/usePriceDelta"
import { computePriceChange } from "@/lib/priceChange"
import { formatPrice } from "@/utils/format"
import Sparkline from "./Sparkline.vue"
import WatchlistButton from "./WatchlistButton.vue"

const props = defineProps<{
  item: Item
  categoryName: string
  isLowest: boolean
  lowestPrice: number | null
}>()

const router = useRouter()
const { currentPrice } = usePriceDelta(props.item)
const specChips = computed(() => specChipTexts(props.item.spec, props.categoryName))
const sparkPoints = computed(() => props.item.history.slice(-30))
const sparkTrend = computed(() => computePriceChange(props.item.history).trend)

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault()
    router.push(`/product/${props.item.id}`)
  }
}

const cardLabel = computed(() => {
  const price = currentPrice.value != null ? formatPrice(currentPrice.value) : "價格未知"
  return `${props.item.name}，目前價格 ${price}`
})
</script>

<template>
  <article
    class="dashboard-card"
    tabindex="0"
    role="button"
    :aria-label="cardLabel"
    @click="router.push(`/product/${item.id}`)"
    @keydown="onKeydown"
  >
    <div class="dc-top">
      <div class="dc-name">{{ item.name }}</div>
      <div class="dc-right">
        <div v-if="item.status === 'gone'" class="dc-gone">已下架</div>
        <template v-else>
          <span v-if="isLowest" class="dc-lowest" title="歷史新低" aria-label="歷史新低">🥇</span>
          <span @click.stop>
            <WatchlistButton :id="item.id" :name="item.name" :price="currentPrice" />
          </span>
        </template>
      </div>
    </div>
    <div v-if="specChips.length" class="dc-specs">
      <span v-for="chip in specChips" :key="chip" class="chip">{{ chip }}</span>
    </div>
    <div class="dc-price">
      <template v-if="item.status === 'gone'">
        <span class="dc-current dc-gone-text">已下架</span>
      </template>
      <template v-else>
        <span class="dc-current">{{ currentPrice != null ? formatPrice(currentPrice) : '—' }}</span>
        <Sparkline :points="sparkPoints" :trend="sparkTrend" :enable-tooltip="true" />
        <span v-if="lowestPrice != null && lowestPrice !== currentPrice" class="dc-history-low">
          歷史最低 {{ formatPrice(lowestPrice) }}
        </span>
      </template>
    </div>
  </article>
</template>

<style scoped>
.dashboard-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.dashboard-card:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-hover);
}

.dc-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.dc-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
}

.dc-name {
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.dc-gone {
  flex: 0 0 auto;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-dim);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 1px 8px;
  background: var(--bg);
}

.dc-lowest {
  font-size: 1.2rem;
  flex: 0 0 auto;
}

.dc-specs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.chip {
  font-size: 0.72rem;
  color: var(--text-dim);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 2px 8px;
  white-space: nowrap;
}

.dc-price {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}

.dc-current {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.dc-history-low {
  font-size: 0.78rem;
  color: var(--text-dim);
}

.dc-gone-text {
  font-size: 1.15rem;
  color: var(--text-dim);
  font-weight: 400;
}

@media (max-width: 639px) {
  .dc-price {
    flex-wrap: wrap;
  }
}
</style>
