// web/src/utils/targetPrice.ts — 目標價輸入驗證（開發規格 004 §2.6 / BDD E6）
// 抽為純函數供 Vitest 覆蓋四組驗證訊息與邊界；view 的 applyTarget 直接消費。
// 規則（BDD Examples 為唯一事實來源）：
//   空白     → 「請輸入目標價」
//   非數字   → 「請輸入有效數字」（abc）
//   0/-100   → 「請輸入大於 0 的有效數字」
//   有效     → ok（含千分位輸入「9,500」→ 9500；允許小數，UIUX §4.3）
export type TargetParseResult =
  | { ok: true; value: number }
  | { ok: false; error: string }

export function parseTargetPrice(raw: string): TargetParseResult {
  const trimmed = raw.trim()
  if (trimmed === "") return { ok: false, error: "請輸入目標價" }
  // 允許「9,500」千分位輸入（BDD happy path 範例）
  const v = Number(trimmed.replace(/,/g, ""))
  if (!Number.isFinite(v)) return { ok: false, error: "請輸入有效數字" }
  if (v <= 0) return { ok: false, error: "請輸入大於 0 的有效數字" }
  return { ok: true, value: v }
}
