// web/src/composables/useFilters.ts — 搜尋＋篩選＋分類狀態（契約 v2）
// 職責：管理三種收斂維度（分類／關鍵字／規格條件）並計算 filteredItems。
// v2 差異：Item 已無 category 欄位 → 分類維度改以「外部分類對照」判定：
//   傳入 itemToCategory（itemId → categoryId map，由 useItems 建立）與 categoryId
//   （目前選中分類，null = 全部，狀態單一來源在 useItems.activeCategoryId）。
// 過濾運算全為純函數（matchesKeyword／matchesCondition），composable 只做狀態組合。

import { ref, computed, type Ref } from "vue"
import type { Item } from "@/types/item"
import type { SpecCondition } from "@/types/filters"
import { matchesKeyword } from "@/utils/search"
import { matchesCondition } from "@/utils/specFilter"

export function useFilters(
  items: Ref<Item[]>, // 已載入商品聚合（lazy 快取：只增不減）
  itemToCategory: Ref<Map<string, string>>, // itemId → categoryId（useItems 前端自建）
  categoryId: Ref<string | null>, // 目前選中分類 id（null = 全部；與 useItems.activeCategoryId 綁定）
) {
  const keyword = ref("") // 原始輸入；比對前 trim + lowercase
  const conditions = ref<SpecCondition[]>([]) // 多條件一律 AND

  /** 過濾管線：分類 → 搜尋 → 規格條件（AND 依序收斂） */
  const filteredItems = computed<Item[]>(() => {
    const q = keyword.value.trim().toLowerCase()
    return items.value.filter(it => {
      // 分類維度：以對照 map 判定（未載入該分類 → 無其 items → 自然不命中）
      if (categoryId.value && itemToCategory.value.get(it.id) !== categoryId.value) return false
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
  /** 直接指寫分類 ref（v2：狀態單一來源為 useItems.activeCategoryId；此處僅 pass-through） */
  function setCategory(id: string | null) { categoryId.value = id }

  return {
    keyword, conditions, categoryId, filteredItems, hasActiveFilter,
    setKeyword, addCondition, removeCondition,
    clearSearch, clearFilters, clearAll, setCategory,
  }
}