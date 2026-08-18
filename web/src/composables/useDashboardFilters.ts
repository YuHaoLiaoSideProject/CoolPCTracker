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

/** 從 spec 取得容量（string type guard） */
function extractCapacity(item: Item): string | null {
  const c = item.spec.capacity
  return typeof c === "string" && c.trim() !== "" ? c : null
}

/** 從 spec 取得轉速（number → string，用於篩選 chip） */
function extractRpm(item: Item): string | null {
  const r = item.spec.rpm
  return typeof r === "number" ? `${r}RPM` : null
}

/** 從 spec 取得記憶體容量（number → string，如 "16GB"） */
function extractRamCapacity(item: Item): string | null {
  const r = item.spec.ram_gb
  return typeof r === "number" ? `${r}GB` : null
}

/** 從 spec 取得 DDR 類型（string，如 "DDR4", "DDR5"） */
function extractDdrType(item: Item): string | null {
  const s = item.spec.spec
  return typeof s === "string" && s.trim() !== "" ? s : null
}

/** 從 spec 取得介面（string，如 "NVMe", "SATA"） */
function extractInterface(item: Item): string | null {
  const i = item.spec.interface
  return typeof i === "string" && i.trim() !== "" ? i : null
}

/** 將容量字串轉為 GB 數值（用於排序）：64GB→64, 1TB→1024 */
function parseCapacityToGB(capacity: string): number {
  const match = capacity.match(/^(\d+(\.\d+)?)\s*(TB|GB|MB)$/i)
  if (!match) return 0
  const num = parseFloat(match[1])
  const unit = match[3].toUpperCase()
  if (unit === "TB") return num * 1024
  if (unit === "MB") return num / 1024
  return num
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
  const selectedCapacities = ref<Set<string>>(new Set())
  const selectedRpms = ref<Set<string>>(new Set())
  const selectedRamCapacities = ref<Set<string>>(new Set())
  const selectedDdrTypes = ref<Set<string>>(new Set())
  const selectedInterfaces = ref<Set<string>>(new Set())

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

  /** 從商品列表中提取唯一容量（已排序，按數值升冪） */
  const availableCapacities = computed<string[]>(() => {
    const set = new Set<string>()
    for (const item of items.value) {
      const capacity = extractCapacity(item)
      if (capacity) set.add(capacity)
    }
    // 按數值排序：64GB, 128GB, 256GB, 512GB, 1TB
    return [...set].sort((a, b) => {
      const numA = parseCapacityToGB(a)
      const numB = parseCapacityToGB(b)
      return numA - numB
    })
  })

  /** 從商品列表中提取唯一轉速（已排序，按數值升冪） */
  const availableRpms = computed<string[]>(() => {
    const set = new Set<string>()
    for (const item of items.value) {
      const rpm = extractRpm(item)
      if (rpm) set.add(rpm)
    }
    // 按數值排序：5400RPM, 7200RPM, 10000RPM
    return [...set].sort((a, b) => {
      const numA = parseInt(a)
      const numB = parseInt(b)
      return numA - numB
    })
  })

  /** 從商品列表中提取唯一記憶體容量（已排序，按數值升冪） */
  const availableRamCapacities = computed<string[]>(() => {
    const set = new Set<string>()
    for (const item of items.value) {
      const cap = extractRamCapacity(item)
      if (cap) set.add(cap)
    }
    return [...set].sort((a, b) => {
      const numA = parseInt(a)
      const numB = parseInt(b)
      return numA - numB
    })
  })

  /** 從商品列表中提取唯一 DDR 類型（已排序） */
  const availableDdrTypes = computed<string[]>(() => {
    const set = new Set<string>()
    for (const item of items.value) {
      const ddr = extractDdrType(item)
      if (ddr) set.add(ddr)
    }
    return [...set].sort()
  })

  /** 從商品列表中提取唯一介面（已排序） */
  const availableInterfaces = computed<string[]>(() => {
    const set = new Set<string>()
    for (const item of items.value) {
      const iface = extractInterface(item)
      if (iface) set.add(iface)
    }
    return [...set].sort()
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

      // 容量篩選（取聯集）
      if (selectedCapacities.value.size > 0) {
        const capacity = extractCapacity(item)
        if (!capacity || !selectedCapacities.value.has(capacity)) return false
      }

      // 轉速篩選（取聯集）
      if (selectedRpms.value.size > 0) {
        const rpm = extractRpm(item)
        if (!rpm || !selectedRpms.value.has(rpm)) return false
      }

      // 記憶體容量篩選（取聯集）
      if (selectedRamCapacities.value.size > 0) {
        const ramCap = extractRamCapacity(item)
        if (!ramCap || !selectedRamCapacities.value.has(ramCap)) return false
      }

      // DDR 類型篩選（取聯集）
      if (selectedDdrTypes.value.size > 0) {
        const ddr = extractDdrType(item)
        if (!ddr || !selectedDdrTypes.value.has(ddr)) return false
      }

      // 介面篩選（取聯集）
      if (selectedInterfaces.value.size > 0) {
        const iface = extractInterface(item)
        if (!iface || !selectedInterfaces.value.has(iface)) return false
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
      selectedBrands.value.size > 0 ||
      selectedCapacities.value.size > 0 ||
      selectedRpms.value.size > 0 ||
      selectedRamCapacities.value.size > 0 ||
      selectedDdrTypes.value.size > 0 ||
      selectedInterfaces.value.size > 0,
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

  function toggleCapacity(capacity: string) {
    const next = new Set(selectedCapacities.value)
    if (next.has(capacity)) {
      next.delete(capacity)
    } else {
      next.add(capacity)
    }
    selectedCapacities.value = next
  }

  function toggleRpm(rpm: string) {
    const next = new Set(selectedRpms.value)
    if (next.has(rpm)) {
      next.delete(rpm)
    } else {
      next.add(rpm)
    }
    selectedRpms.value = next
  }

  function toggleRamCapacity(ramCap: string) {
    const next = new Set(selectedRamCapacities.value)
    if (next.has(ramCap)) {
      next.delete(ramCap)
    } else {
      next.add(ramCap)
    }
    selectedRamCapacities.value = next
  }

  function toggleDdrType(ddr: string) {
    const next = new Set(selectedDdrTypes.value)
    if (next.has(ddr)) {
      next.delete(ddr)
    } else {
      next.add(ddr)
    }
    selectedDdrTypes.value = next
  }

  function toggleInterface(iface: string) {
    const next = new Set(selectedInterfaces.value)
    if (next.has(iface)) {
      next.delete(iface)
    } else {
      next.add(iface)
    }
    selectedInterfaces.value = next
  }

  /** 清除篩選（保留排序） */
  function clearFilters() {
    priceMin.value = null
    priceMax.value = null
    selectedBrands.value = new Set()
    selectedCapacities.value = new Set()
    selectedRpms.value = new Set()
    selectedRamCapacities.value = new Set()
    selectedDdrTypes.value = new Set()
    selectedInterfaces.value = new Set()
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
    selectedCapacities,
    selectedRpms,
    selectedRamCapacities,
    selectedDdrTypes,
    selectedInterfaces,
    // derived
    availableBrands,
    availableCapacities,
    availableRpms,
    availableRamCapacities,
    availableDdrTypes,
    availableInterfaces,
    filteredItems,
    sortedItems,
    hasActiveFilter,
    // actions
    setSortMode,
    setPriceMin,
    setPriceMax,
    toggleBrand,
    toggleCapacity,
    toggleRpm,
    toggleRamCapacity,
    toggleDdrType,
    toggleInterface,
    clearFilters,
    resetAll,
  }
}
