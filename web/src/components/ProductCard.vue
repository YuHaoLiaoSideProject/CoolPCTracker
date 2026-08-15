<script setup lang="ts">
// web/src/components/ProductCard.vue — 商品卡片（開發規格 003 §2.10）
// 004/005 整合點集中於此元件：open / toggle-watch / toggle-compare 事件出口。
// 卡片 tabindex=0 + Enter/Space 可觸發 open（004 前即具鍵盤可操作性，UIUX §7.7）。
import { computed } from "vue"
import type { Item } from "@/types/item"
import { usePriceDelta, specChipTexts } from "@/composables/usePriceDelta"
import Sparkline from "./Sparkline.vue"
import { formatPrice } from "@/utils/format"

const props = defineProps<{
  item: Item
  watched?: boolean // 005：已追蹤狀態（005 實作前預設 false）
  compareSelected?: boolean // 005：比價已勾選
}>()

const emit = defineEmits<{
  (e: "open", item: Item): void // 004：點名稱/卡片 → 詳情頁
  (e: "toggle-watch", item: Item): void // 005：追蹤按鈕切換
  (e: "toggle-compare", item: Item): void // 005：比價勾選切換
}>()

const { currentPrice, deltaClass, deltaText } = usePriceDelta(props.item)
const sparkPoints = computed(() => props.item.history.slice(-30)) // 卡片取最近 30 點
const specChips = computed(() => specChipTexts(props.item.spec, props.item.category))

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault()
    emit("open", props.item)
  }
}

const cardLabel = computed(() => {
  const price = currentPrice.value != null ? formatPrice(currentPrice.value) : "價格未知"
  return `${props.item.name}，目前價格 ${price}，${deltaText.value}`
})
</script>

<template>
  <article
    class="product-card"
    tabindex="0"
    role="button"
    :aria-label="cardLabel"
    @click="emit('open', item)"
    @keydown="onKeydown"
  >
    <div class="pc-top">
      <div class="pc-name">{{ item.name }}</div>
      <div v-if="item.status === 'gone'" class="pc-gone" title="已下架">已下架</div>
    </div>
    <div v-if="specChips.length" class="pc-specs">
      <span v-for="chip in specChips" :key="chip" class="chip">{{ chip }}</span>
    </div>
    <Sparkline :points="sparkPoints" />
    <div class="pc-price">
      <span class="pc-current">{{ currentPrice != null ? formatPrice(currentPrice) : "價格未知" }}</span>
      <span class="pc-delta" :class="deltaClass">{{ deltaText }}</span>
    </div>
    <div class="pc-actions">
      <button
        type="button"
        class="pc-btn"
        :class="{ 'is-active': watched }"
        :aria-pressed="!!watched"
        @click.stop="emit('toggle-watch', item)"
      >
        {{ watched ? "已追蹤" : "追蹤" }}
      </button>
      <button
        type="button"
        class="pc-btn"
        :class="{ 'is-active': compareSelected }"
        :aria-pressed="!!compareSelected"
        @click.stop="emit('toggle-compare', item)"
      >
        {{ compareSelected ? "已勾選" : "比價" }}
      </button>
    </div>
  </article>
</template>

<style scoped>
.product-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  cursor: pointer; /* 004：點卡片進詳情 */
  transition: border-color 0.15s, box-shadow 0.15s;
}

.product-card:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-hover);
}

.pc-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.pc-name {
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.pc-gone {
  flex: 0 0 auto;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-dim);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 1px 8px;
  background: var(--bg);
}

.pc-specs {
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

.pc-price {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.pc-current {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.pc-delta {
  font-size: 0.85rem;
  font-weight: 600;
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

.pc-actions {
  display: flex;
  gap: 8px;
  margin-top: auto;
}

.pc-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  padding: 0 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text-dim);
  font-size: 0.78rem;
  font-weight: 600;
  transition: background-color var(--transition), color var(--transition),
    border-color var(--transition);
}

.pc-btn:hover {
  color: var(--text);
  border-color: var(--brand);
}

.pc-btn.is-active {
  background: var(--brand-soft);
  color: var(--brand);
  border-color: var(--brand);
}

@media (max-width: 639px) {
  .pc-price {
    flex-wrap: wrap;
  }

  .pc-btn {
    height: var(--h-mobile);
    flex: 1;
  }
}
</style>
