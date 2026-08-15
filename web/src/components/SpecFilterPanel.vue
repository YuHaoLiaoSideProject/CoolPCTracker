<script setup lang="ts">
// web/src/components/SpecFilterPanel.vue — 規格篩選面板（開發規格 003 §2.9）
// 數值門檻表單（欄位下拉 + ≥ + 數值 + 單位）、已套用條件 chips（可單獨移除）。
// 每個欄位一次只能有一個條件（重複套用 → 取代，見 useFilters.addCondition）。
import { ref } from "vue"
import type { SpecCondition, SpecField } from "@/types/filters"
import { FILTERABLE_FIELDS, parseCondition } from "@/utils/specFilter"

const props = defineProps<{ conditions: SpecCondition[] }>()
const emit = defineEmits<{
  (e: "add", c: SpecCondition): void
  (e: "remove", id: string): void
}>()

const field = ref<SpecField>("vram_gb")
const value = ref<number | null>(null)
const error = ref("")

function apply() {
  if (value.value == null || Number.isNaN(value.value)) {
    error.value = "請輸入有效數值門檻（≥）"
    return
  }
  const unit = FILTERABLE_FIELDS.find(f => f.field === field.value)?.unit ?? ""
  const c = parseCondition(`${FILTERABLE_FIELDS.find(f => f.field === field.value)?.label ?? field.value}≥${value.value}${unit}`)
  if (!c) {
    error.value = "請輸入有效數值門檻（≥）"
    return
  }
  error.value = ""
  value.value = null
  emit("add", c)
}
</script>

<template>
  <section class="spec-filter" aria-label="規格篩選">
    <div class="spec-filter-head">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z" />
      </svg>
      <span>規格篩選</span>
      <span class="hint">多條件為 AND 交集</span>
    </div>

    <form class="spec-form" @submit.prevent="apply">
      <select v-model="field" aria-label="規格欄位">
        <option v-for="f in FILTERABLE_FIELDS" :key="f.field" :value="f.field">
          {{ f.label }}
        </option>
      </select>
      <span class="op">≥</span>
      <input
        v-model.number="value"
        type="number"
        class="spec-value"
        inputmode="decimal"
        :aria-label="`門檻數值（${FILTERABLE_FIELDS.find(f => f.field === field)?.unit ?? ''}）`"
        placeholder="0"
      />
      <span class="unit">{{ FILTERABLE_FIELDS.find(f => f.field === field)?.unit ?? "" }}</span>
      <button type="submit" class="btn btn-primary">套用篩選</button>
    </form>

    <p v-if="error" class="spec-err" role="alert">{{ error }}</p>

    <div v-if="props.conditions.length" class="cond-chips">
      <span v-for="c in props.conditions" :key="c.id" class="fchip">
        <span>{{ c.label }}</span>
        <button
          type="button"
          class="fchip-remove"
          :aria-label="`移除條件 ${c.label}`"
          @click="emit('remove', c.id)"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </span>
    </div>
  </section>
</template>

<style scoped>
.spec-filter {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.spec-filter-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-dim);
}

.spec-filter-head svg {
  color: var(--brand);
}

.spec-filter-head .hint {
  font-weight: 400;
  color: var(--text-dim);
  opacity: 0.85;
}

.spec-form {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.spec-form select,
.spec-form .spec-value {
  height: var(--h);
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  transition: border-color var(--transition);
}

.spec-form select {
  max-width: 150px;
}

.spec-form .spec-value {
  width: 90px;
}

.spec-form select:focus,
.spec-form .spec-value:focus {
  border-color: var(--accent);
  outline: none;
}

.spec-form .op {
  font-weight: 700;
  color: var(--text);
}

.spec-form .unit {
  color: var(--text-dim);
  font-size: 0.82rem;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: var(--h);
  padding: 0 14px;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  font-size: 0.86rem;
  font-weight: 600;
  transition: background-color var(--transition), border-color var(--transition);
}

.btn-primary {
  background: var(--brand);
  color: #fff;
}

.btn-primary:hover {
  filter: brightness(1.05);
}

.spec-err {
  color: var(--danger);
  font-size: 0.8rem;
}

.cond-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.fchip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  height: 28px;
  padding: 0 4px 0 12px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 0.8rem;
  font-weight: 600;
}

.fchip-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: currentColor;
  transition: background-color var(--transition);
}

.fchip-remove:hover {
  background: rgba(31, 111, 235, 0.15);
}

/* 手機：控制高度 44px */
@media (max-width: 639px) {
  .spec-form select,
  .spec-form .spec-value,
  .spec-form .btn {
    height: var(--h-mobile);
  }

  .spec-form select {
    max-width: none;
    flex: 1 1 45%;
  }

  .spec-form .btn {
    flex: 1 1 100%;
  }
}
</style>
