// web/src/composablesuseDashboard.ts — Dashboard 展示邏輯（017 + 019 擴充）
// 017：排序 + Top 10 + isLowest/lowestPrice
// 019：新增 activeCategory + categoryLoading + switchCategory

import { computed, type Ref } from "vue"
import type { Item, CategoryMeta } from "@/types/item"
import { useItems } from "@/composables/useItems"

/** Dashboard 卡片用商品（擴展 Item 加計算欄位） */
export interface DashboardItem {
  item: Item
  currentPrice: number | null
  isLowest: boolean
  lowestPrice: number | null
}

/**
 * Dashboard 展示邏輯 composable
 * @param items — 已過濾的目前分類商品（由 DashboardView 用 itemToCategory 過濾）
 * @param categoryId — 目前選中分類 id
 * @param resetGroup — 重置分組的回呼（由 useSpecGroups.resetGroup 傳入）
 */
export function useDashboard(
  items: Ref<Item[]>,
  categoryId: Ref<string | null>,
  resetGroup?: () => void,
) {
  const itemsState = useItems()

  /** 計算單一商品的目前價格（history 最後一筆 p） */
  function extractCurrentPrice(item: Item): number | null {
    return item.history.length > 0 ? item.history[item.history.length - 1].p : null
  }

  /** 歷史最低價 Map：Map<分類id, { price, itemId }> */
  const categoryLowest = computed(() => {
    const map = new Map<string, { price: number; itemId: string }>()
    for (const item of items.value) {
      if (item.history.length === 0) continue
      const price = item.history[item.history.length - 1].p
      const existing = map.get(categoryId.value ?? "")
      if (!existing || price < existing.price) {
        map.set(categoryId.value ?? "", { price, itemId: item.id })
      }
    }
    return map
  })

  /** 目前選中分類的商品列表（按 currentPrice 升冪 + Top 10 + 填入 isLowest/lowestPrice） */
  const dashboardItems = computed<DashboardItem[]>(() => {
    const id = categoryId.value
    if (id == null) return []
    const lowest = categoryLowest.value.get(id)
    return items.value
      .map((item) => ({
        item,
        currentPrice: extractCurrentPrice(item),
        isLowest: lowest != null && item.id === lowest.itemId,
        lowestPrice: lowest?.price ?? null,
      }))
      .sort((a, b) => {
        if (a.currentPrice == null) return 1
        if (b.currentPrice == null) return -1
        return a.currentPrice - b.currentPrice
      })
      .slice(0, 10)
  })

  // —— 019 新增 ——

  /** 目前分類資訊（供 CategoryTabs 高亮用） */
  const activeCategory = computed<CategoryMeta | null>(() => {
    const id = categoryId.value
    return id ? itemsState.categories.value.find((c) => c.id === id) ?? null : null
  })

  /** 分類級載入中判定（Spinner 顯示用） */
  const categoryLoading = computed<boolean>(() => {
    const id = categoryId.value
    return id ? itemsState.isLoadingCategory(id) : false
  })

  /** 切換分類（含分組重置） */
  async function switchCategory(newId: string): Promise<void> {
    await itemsState.loadCategory(newId)
    resetGroup?.()
  }

  return {
    dashboardItems,
    extractCurrentPrice,
    categoryLowest,
    activeCategory,
    categoryLoading,
    switchCategory,
  }
}
