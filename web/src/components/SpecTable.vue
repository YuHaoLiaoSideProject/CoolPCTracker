<script setup lang="ts">
// web/src/components/SpecTable.vue — 規格表（開發規格 004 §2.6 / BDD E10）
// 兩欄 grid（欄位名：值）；空值（null/undefined/''）欄位整列不渲染；
// key 經 SPEC_LABELS 對照顯示中文，未知 key 顯示原始 key；順序維持物件鍵序。
import { computed } from "vue"
import type { ItemSpec } from "@/types/item"

const props = defineProps<{ spec: ItemSpec }>()

// 欄位名中文對照（spec_parser 產出 key；004 §2.6 白名單 + 003 ItemSpec 擴充欄位）
const SPEC_LABELS: Record<string, string> = {
  brand: "品牌",
  model: "型號",
  cores: "核心數",
  threads: "執行緒",
  base_ghz: "基礎時脈(GHz)",
  turbo_ghz: "超頻時脈(GHz)",
  tdp_w: "功耗 TDP(W)",
  socket: "腳位",
  vram_gb: "VRAM(GB)",
  wattage_w: "功耗(W)",
  capacity_gb: "儲存容量(GB)",
  ram_gb: "記憶體(GB)",
  chip: "晶片",
  interface: "介面",
  clock_mhz: "時脈(MHz)",
  rpm: "轉速(RPM)",
  chipset: "晶片組",
  form_factor: "版型",
  spec: "規格摘要",
  usage: "用途",
  summary: "摘要",
}

const rows = computed(() =>
  Object.entries(props.spec)
    .filter(([, v]) => v != null && v !== "")
    .map(([k, v]) => ({ key: k, label: SPEC_LABELS[k] ?? k, value: String(v) })),
)
</script>

<template>
  <dl v-if="rows.length" class="spec-table">
    <template v-for="row in rows" :key="row.key">
      <dt class="spec-key">{{ row.label }}</dt>
      <dd class="spec-value">{{ row.value }}</dd>
    </template>
  </dl>
  <p v-else class="spec-empty">無規格資訊</p>
</template>

<style scoped>
.spec-table {
  display: grid;
  grid-template-columns: 140px 1fr;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  margin: 0;
  background: var(--surface);
}

.spec-key {
  background: var(--surface-2);
  padding: 8px 14px;
  font-size: 13px;
  color: var(--text-dim);
  border-bottom: 1px solid var(--border);
  margin: 0;
}

.spec-value {
  padding: 8px 14px;
  font-size: 14px;
  border-bottom: 1px solid var(--border);
  margin: 0;
  word-break: break-word;
}

.spec-table > :nth-last-child(-n + 2) {
  border-bottom: none;
}

.spec-empty {
  padding: 20px 14px;
  font-size: 13px;
  color: var(--text-dim);
  background: var(--surface);
  border: 1px dashed var(--border);
  border-radius: var(--radius);
}

@media (max-width: 767px) {
  .spec-table {
    grid-template-columns: 120px 1fr;
  }
}
</style>
