// web/src/composables/useFilters.ts — 搜尋＋篩選＋分類狀態（開發規格 003 §2.5）
// 職責：管理三種收斂維度（分類／關鍵字／規格條件）並計算 filteredItems。
// 過濾運算全為純函數（matchesKeyword／matchesCondition），composable 只做狀態組合。

import { ref, computed, type Ref } from "vue"
import type { Item } from "@/types/item"
import type { SpecCondition } from "@/types/filters"
import { matchesKeyword } from "@/utils/search"
import { matchesCondition } from "@/utils/specFilter"
import { labelOf } from "@/data/categories"

export function useFilters(items: Ref<Item[]>) {
  const keyword = ref("") // 原始輸入；比對前 trim + lowercase
  const conditions = ref<SpecCondition[]>([]) // 多條件一律 AND
  const categoryKey = ref<string | null>(null) // null = 全部

  /** 過濾管線：分類 → 搜尋 → 規格條件（AND 依序收斂） */
  const filteredItems = computed<Item[]>(() => {
    const q = keyword.value.trim().toLowerCase()
    return items.value.filter(it => {
      if (categoryKey.value && it.category !== labelOf(categoryKey.value as never)) return false
      if (q && !matchesKeyword(it, q)) return false
      return conditions.value.every(c => matchesCondition(it, c))
    })
  })

  const hasActiveFilter = computed(
    () => keyword.value.trim() !== "" || conditions.value.length > 0,
  )

  function setKeyword(v: string) { keyword.value = v }
  function addCondition(c: SpecCondition) {
    // 同欄位重複套用 → 取代（保留較新值），避免混淆；其餘保留
    conditions.value = [...conditions.value.filter(x => x.field !== c.field), c]
  }
  function removeCondition(id: string) { conditions.value = conditions.value.filter(c => c.id !== id) }
  function clearSearch() { keyword.value = "" }
  function clearFilters() { conditions.value = [] }
  /** 清除全部條件：僅清搜尋+篩選，**保留目前分類**（BDD：回到目前分類的完整集合） */
  function clearAll() { keyword.value = ""; conditions.value = [] }
  function setCategory(key: string | null) { categoryKey.value = key }

  return {
    keyword, conditions, categoryKey, filteredItems, hasActiveFilter,
    setKeyword, addCondition, removeCondition,
    clearSearch, clearFilters, clearAll, setCategory,
  }
}
