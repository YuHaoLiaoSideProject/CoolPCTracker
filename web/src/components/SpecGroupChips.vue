<!-- web/src/components/SpecGroupChips.vue — 分組 Chips UI（開發規格 018 §2.4）-->
<!-- 折疊 >8 個 → 顯示前 7 個 + 「更多 ▼」；展開後顯示全部 + 「收起 ▲」-->
<script setup lang="ts">
import { ref, computed } from "vue"
import type { GroupOption } from "@/types/specGroup"

const COLLAPSE_THRESHOLD = 8

const props = defineProps<{
  groups: GroupOption[]
  selectedKey: string
}>()

const emit = defineEmits<{
  (e: "select", key: string): void
}>()

const isExpanded = ref(false)

const needsCollapse = computed(() => props.groups.length > COLLAPSE_THRESHOLD)

const visibleGroups = computed(() => {
  if (!needsCollapse.value || isExpanded.value) return props.groups
  return props.groups.slice(0, COLLAPSE_THRESHOLD - 1) // 前 7 個
})

const collapseLabel = computed(() => {
  const hiddenCount = props.groups.length - (COLLAPSE_THRESHOLD - 1)
  return isExpanded.value ? "收起 ▲" : `更多 (${hiddenCount}) ▼`
})

function toggleExpand(): void {
  isExpanded.value = !isExpanded.value
}

function handleSelect(key: string): void {
  emit("select", key)
}
</script>

<template>
  <div class="spec-group-chips" role="group" aria-label="規格分組">
    <button
      v-for="group in visibleGroups"
      :key="group.key"
      type="button"
      class="chip"
      :class="{ 'chip--active': selectedKey === group.key }"
      :aria-pressed="selectedKey === group.key"
      @click="handleSelect(group.key)"
    >
      <span class="chip__label">{{ group.label }}</span>
      <span class="chip__count">{{ group.count }}</span>
    </button>
    <button
      v-if="needsCollapse"
      type="button"
      class="chip chip--toggle"
      @click="toggleExpand"
    >
      {{ collapseLabel }}
    </button>
  </div>
</template>

<style scoped>
.spec-group-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 0;
}

.chip {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 14px;
  border-radius: 18px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-dim);
  font-size: 0.82rem;
  cursor: pointer;
  transition: all var(--transition);
  white-space: nowrap;
}

.chip:hover {
  border-color: var(--brand);
  color: var(--brand);
}

.chip--active {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
  font-weight: 600;
}

.chip--active:hover {
  background: var(--brand);
  color: #fff;
}

.chip__label {
  margin-right: 4px;
}

.chip__count {
  font-size: 0.72rem;
  opacity: 0.7;
}

.chip--toggle {
  background: none;
  border: none;
  color: var(--brand);
  font-size: 0.82rem;
  font-weight: 500;
  padding: 0 12px;
}

.chip--toggle:hover {
  background: var(--brand-soft);
}

@media (max-width: 768px) {
  .spec-group-chips {
    overflow-x: auto;
    flex-wrap: nowrap;
    scrollbar-width: thin;
    -webkit-overflow-scrolling: touch;
  }
  .chip {
    flex: 0 0 auto;
  }
}

@media (max-width: 639px) {
  .chip {
    height: var(--h-mobile);
  }
}
</style>
