// web/src/utils/search.ts — 全文搜尋（開發規格 003 §2.6）
// 僅比對 name + spec 欄位值（不區分大小寫、子字串字面比對）。
// 不含 flags / status / history（BDD：搜尋「9999」不得命中歷史價 9999 的商品）。

import type { Item } from "@/types/item"

export function matchesKeyword(it: Item, q: string): boolean {
  const needle = q.toLowerCase() // 不區分大小寫（BDD）；useFilters 亦已 trim+lowercase，此處防禦性再轉一次
  if (it.name.toLowerCase().includes(needle)) return true
  // spec 可能為空物件 → join 後為 ''，不命中（無規格欄位商品仍可被名稱搜尋命中）
  const specText = Object.values(it.spec)
    .map(v => String(v ?? ""))
    .join(" ")
    .toLowerCase()
  return specText.includes(needle)
}
