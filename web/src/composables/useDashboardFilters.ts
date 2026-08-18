// web/src/composables/useDashboardFilters.ts — Dashboard 篩選 + 排序 composable（022）
// 職責：管理 sortMode / priceMin / priceMax / selectedBrands 並計算
//       filteredItems（價格+品牌篩選）與 sortedItems（篩選後排序）。

import { ref, computed, watch, type Ref } from "vue"
import type { Item } from "@/types/item"
import type { SortMode } from "@/types/dashboardFilter"

/** 從 history 取得最後一筆價格；無 history 回傳 null */
function extractPrice(item: Item): number | null {
  return item.history.length > 0 ? item.history[item.history.length - 1].p : null
}

/** 從 spec 取得品牌（string type guard） */
function extractBrand(item: Item): string | null {
  const b = item.spec.brand
  return typeof b === "string" && b.trim() !== "" ? b : null
}

/**
 * Dashboard 篩選 + 排序 composable
 * @param items — 已按分類過濾的商品（由上游傳入）
 */
export function useDashboardFilters(items: Ref<Item[]>) {
  const sortMode = ref<SortMode>("price_asc")
  const priceMin = ref<number | null>(null)
  const priceMax = ref<number | null>(null)
  const selectedBrands = ref<Set<string>>(new Set())

  // ── auto-swap min/max ──────────────────────────────
  watch([priceMin, priceMax], ([min, max]) => {
    if (min != null && max != null && min > max) {
      priceMin.value = max
      priceMax.value = min
    }
  })

  // ── derived ────────────────────────────────────────

  /** 從商品列表中提取唯一品牌（已排序） */
  const availableBrands = computed<string[]>(() => {
    const set = new Set<string>()
    for (const item of items.value) {
      const brand = extractBrand(item)
      if (brand) set.add(brand)
    }
    return [...set].sort((a, b) => a.localeCompare(b, "zh-Hant"))
  })

  /** 價格 + 品牌篩選（不含排序） */
  const filteredItems = computed<Item[]>(() => {
    const min = priceMin.value
    const max = priceMax.value
    const brands = selectedBrands.value

    return items.value.filter((item) => {
      // 價格範圍篩選
      const price = extractPrice(item)
      if (min != null && (price == null || price < min)) return false
      if (max != null && (price == null || price > max)) return false

      // 品牌篩選（取聯集：勾選 A 或 B 的商品皆顯示）
      if (brands.size > 0) {
        const brand = extractBrand(item)
        if (!brand || !brands.has(brand)) return false
      }

      return true
    })
  })

  /** 篩選後排序 */
  const sortedItems = computed<Item[]>(() => {
    const mode = sortMode.value
    const list = [...filteredItems.value]

    list.sort((a, b) => {
      if (mode === "recently_updated") {
        // last_seen desc
        return b.last_seen.localeCompare(a.last_seen)
      }

      // price sort：null 置底
      const pa = extractPrice(a)
      const pb = extractPrice(b)
      if (pa == null && pb == null) return 0
      if (pa == null) return 1
      if (pb == null) return -1

      return mode === "price_asc" ? pa - pb : pb - pa
    })

    return list
  })

  /** 是否有 active 篩選（不含排序） */
  const hasActiveFilter = computed<boolean>(
    () =>
      priceMin.value != null ||
      priceMax.value != null ||
      selectedBrands.value.size > 0,
  )

  // ── actions ────────────────────────────────────────

  function setSortMode(mode: SortMode) {
    sortMode.value = mode
  }

  function setPriceMin(value: number | null) {
    priceMin.value = value
  }

  function setPriceMax(value: number | null) {
    priceMax.value = value
  }

  function toggleBrand(brand: string) {
    const next = new Set(selectedBrands.value)
    if (next.has(brand)) {
      next.delete(brand)
    } else {
      next.add(brand)
    }
    selectedBrands.value = next
  }

  /** 清除篩選（保留排序） */
  function clearFilters() {
    priceMin.value = null
    priceMax.value = null
    selectedBrands.value = new Set()
  }

  /** 重置全部（含排序） */
  function resetAll() {
    sortMode.value = "price_asc"
    clearFilters()
  }

  return {
    // state
    sortMode,
    priceMin,
    priceMax,
    selectedBrands,
    // derived
    availableBrands,
    filteredItems,
    sortedItems,
    hasActiveFilter,
    // actions
    setSortMode,
    setPriceMin,
    setPriceMax,
    toggleBrand,
    clearFilters,
    resetAll,
  }
}
