// web/src/composables/useSpecGroups.ts — 規格分組 composable（開發規格 018 §2.3）
// 接收 items + categoryName，輸出 groups / hasGroups / selectedGroupKey / groupedItems / selectGroup / resetGroup
import { ref, computed, toValue, type MaybeRefOrGetter } from "vue"
import type { Item } from "@/types/item"
import { GROUP_STRATEGY, ALL_GROUP_KEY, OTHER_GROUP_KEY, type GroupOption } from "@/types/specGroup"

/**
 * 規格分組 composable
 * @param items — 目前分類的商品列表（Ref 或 getter）
 * @param categoryName — 目前分類名稱（如 "記憶體"），用於查詢 GROUP_STRATEGY
 */
export function useSpecGroups(
  items: MaybeRefOrGetter<Item[]>,
  categoryName: MaybeRefOrGetter<string | null>,
) {
  const rawItems = computed(() => toValue(items))
  const category = computed(() => toValue(categoryName))

  /** 該分類的分組策略（null = 不支援分組） */
  const strategy = computed(() => {
    const cat = category.value
    return cat != null && cat in GROUP_STRATEGY ? GROUP_STRATEGY[cat] : null
  })

  /** 每件商品的分組鍵 */
  const itemGroupKeyMap = computed(() => {
    const strat = strategy.value
    if (!strat) return new Map<string, string>()
    const map = new Map<string, string>()
    for (const item of rawItems.value) {
      const key = strat.formatKey(item.spec) ?? OTHER_GROUP_KEY
      map.set(item.id, key)
    }
    return map
  })

  /** 收集唯一分組鍵（排除「其他」+「全部」）→ 排序 */
  const uniqueKeys = computed(() => {
    const keys = new Set<string>()
    for (const gk of itemGroupKeyMap.value.values()) {
      if (gk !== OTHER_GROUP_KEY) keys.add(gk)
    }
    return [...keys].sort()
  })

  /** 分組選項列表（含「全部」；「其他」不顯示在 Chips 中） */
  const groups = computed<GroupOption[]>(() => {
    if (!strategy.value) return []
    const total = rawItems.value.length
    const allGroup: GroupOption = { key: ALL_GROUP_KEY, label: "全部", count: total }
    const keyCounts = new Map<string, number>()
    for (const gk of itemGroupKeyMap.value.values()) {
      if (gk !== OTHER_GROUP_KEY) {
        keyCounts.set(gk, (keyCounts.get(gk) ?? 0) + 1)
      }
    }
    const specGroups: GroupOption[] = uniqueKeys.value.map((key) => ({
      key,
      label: key,
      count: keyCounts.get(key) ?? 0,
    }))
    return [allGroup, ...specGroups]
  })

  /** 是否支援分組（true → 顯示 Chips） */
  const hasGroups = computed(() => {
    return strategy.value !== null && groups.value.length >= 2
  })

  /** 目前選取的分組 key（空字串 = 「全部」） */
  const selectedGroupKey = ref<string>(ALL_GROUP_KEY)

  /** 分組篩選後的商品列表（按價格由低到高排序） */
  const groupedItems = computed<Item[]>(() => {
    const strat = strategy.value
    const items = rawItems.value
    const selected = selectedGroupKey.value
    const sortByPrice = (a: Item, b: Item) => {
      const priceA = a.history.length > 0 ? a.history[a.history.length - 1].p : Infinity
      const priceB = b.history.length > 0 ? b.history[b.history.length - 1].p : Infinity
      return priceA - priceB
    }
    if (!strat || selected === ALL_GROUP_KEY) {
      return [...items].sort(sortByPrice)
    }
    return items
      .filter((item) => itemGroupKeyMap.value.get(item.id) === selected)
      .sort(sortByPrice)
  })

  /** 切換分組 */
  function selectGroup(key: string): void {
    selectedGroupKey.value = key
  }

  /** 回到「全部」 */
  function resetGroup(): void {
    selectedGroupKey.value = ALL_GROUP_KEY
  }

  return { groups, hasGroups, selectedGroupKey, groupedItems, selectGroup, resetGroup }
}
