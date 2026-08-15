// web/src/composables/__tests__/useCrawledAt.test.ts — BDD E11 台北時間／過期規則
import { describe, expect, it } from "vitest"
import { computed, ref } from "vue"
import { formatCrawledAt, isCrawledAtStale, useCrawledAt } from "@/composables/useCrawledAt"

describe("formatCrawledAt（E11：UTC → 台北時間 YYYY-MM-DD HH:mm）", () => {
  it("2026-08-15T06:00:00Z → 2026-08-15 14:00（台北 UTC+8）", () => {
    expect(formatCrawledAt("2026-08-15T06:00:00Z")).toBe("2026-08-15 14:00")
  })

  it("跨日案例：UTC 前一日深夜 → 台北當日", () => {
    expect(formatCrawledAt("2026-08-14T16:30:00Z")).toBe("2026-08-15 00:30")
  })

  it("空值/非法輸入不拋錯", () => {
    expect(formatCrawledAt(undefined)).toBe("未知")
    expect(formatCrawledAt(null)).toBe("未知")
    expect(formatCrawledAt("not-a-date")).toBe("not-a-date")
  })
})

describe("isCrawledAtStale（> 7 天過期，與 003 isStale 同規則）", () => {
  const daysAgo = (n: number): string => new Date(Date.now() - n * 86_400_000).toISOString()

  it("8 天前 → true；7 天整 → false（超過 7 天才算）", () => {
    expect(isCrawledAtStale(daysAgo(8))).toBe(true)
    expect(isCrawledAtStale(daysAgo(7))).toBe(false)
  })

  it("近期 → false；空值/非法 → false", () => {
    expect(isCrawledAtStale(daysAgo(1))).toBe(false)
    expect(isCrawledAtStale(undefined)).toBe(false)
    expect(isCrawledAtStale("garbage")).toBe(false)
  })
})

describe("useCrawledAt（響應式：getter 輸入）", () => {
  it("crawled_at 變化時 updatedLabel 同步", () => {
    const crawledAt = ref<string | null>("2026-08-15T06:00:00Z")
    const { updatedLabel, isStale } = useCrawledAt(crawledAt)
    expect(updatedLabel.value).toBe("2026-08-15 14:00")
    expect(isStale.value).toBe(false)
    crawledAt.value = daysAgoHelper(9)
    expect(isStale.value).toBe(true)
  })

  it("computed getter 輸入亦可", () => {
    const meta = ref<{ crawled_at: string } | null>({ crawled_at: "2026-08-15T06:00:00Z" })
    const { updatedLabel } = useCrawledAt(computed(() => meta.value?.crawled_at))
    expect(updatedLabel.value).toBe("2026-08-15 14:00")
    meta.value = null
    expect(updatedLabel.value).toBe("未知")
  })
})

function daysAgoHelper(n: number): string {
  return new Date(Date.now() - n * 86_400_000).toISOString()
}
