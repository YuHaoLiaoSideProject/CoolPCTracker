// web/e2e/003-filtering.spec.ts — 003「列表＋搜尋篩選」篩選功能 E2E
// 以真實資料（依 api/index.json 的 categories[] 目錄逐一載入 api/items/{file} 聚合，
// 並以 crawled_at 組 ?v= 快取穿透 URL）計算 oracle，避免寫死隨資料漂移的筆數。
// v2：列表頁預設僅載入第一個分類 → gotoListing 改以 ?category=all 進入「全部」視圖
// （loadAll() 全分類聚合），維持既有「全商品集合」篩選斷言語意。
// 涵蓋：單一規格篩選、多條件 AND、搜尋＋篩選並用、清除全部、無結果空狀態、
//       邊界值納入（≥ 語意）、無規格欄位商品靜默排除。
import { test, expect, type Page } from "@playwright/test"
import {
  loadItems,
  matchesKeyword,
  flatSpec,
  applyConditions,
  filterByKeywordAndConditions,
  sortedNames,
  type RawItem,
} from "./helpers/oracle"

const ITEMS: RawItem[] = loadItems()
const TOTAL = ITEMS.length

/** 開啟列表頁「全部」視圖並等待資料載入完成（pl-count 顯示總筆數）
 *  v2：預設視圖僅載入第一個分類；?category=all → loadAll() 全分類聚合 */
async function gotoListing(page: Page): Promise<void> {
  await page.goto("/CoolPCTracker/#/?category=all")
  await expect(page.locator(".pl-count b")).toHaveText(String(TOTAL))
}

/** 在規格篩選面板套用「欄位 ≥ 數值」條件 */
async function applyFilter(page: Page, field: string, value: number): Promise<void> {
  await page.selectOption('select[aria-label="規格欄位"]', field)
  await page.fill("input.spec-value", String(value))
  await page.getByRole("button", { name: "套用篩選" }).click()
}

/** 於搜尋框輸入關鍵字（SearchBar 有 300ms debounce，後續以 count 斷言自動等待） */
async function search(page: Page, keyword: string): Promise<void> {
  await page.fill("input.search-input", keyword)
}

/** 讀取目前列表渲染出的商品名稱（排序後，供集合相等斷言） */
async function renderedNames(page: Page): Promise<string[]> {
  const names = await page.locator(".pc-name").allTextContents()
  return names.map(n => n.trim()).sort()
}

test.describe("003 規格篩選 E2E（真資料 oracle）", () => {
  test("套用單一規格篩選 VRAM≥12G：結果集合正確", async ({ page }) => {
    await gotoListing(page)
    const oracle = applyConditions(ITEMS, [{ field: "vram_gb", threshold: 12 }])
    expect(oracle.length).toBeGreaterThan(0)

    await applyFilter(page, "vram_gb", 12)

    await expect(page.locator(".cond-chips .fchip", { hasText: "VRAM≥12G" })).toBeVisible()
    await expect(page.locator(".pl-count b")).toHaveText(String(oracle.length))
    expect(await renderedNames(page)).toEqual(sortedNames(oracle))
  })

  test("套用單一規格篩選 瓦數≥750W：真資料無 wattage_w → 空狀態（資料缺口）", async ({ page }) => {
    await gotoListing(page)
    const oracle = applyConditions(ITEMS, [{ field: "wattage_w", threshold: 750 }])
    // 現況：目前資料版本沒有任何 wattage_w 欄位（9 大分類不含電源），故 oracle 為空集合
    expect(oracle.length).toBe(0)

    await applyFilter(page, "wattage_w", 750)

    await expect(page.locator(".cond-chips .fchip", { hasText: "瓦數≥750W" })).toBeVisible()
    await expect(page.locator(".pl-count b")).toHaveText("0")
    await expect(page.locator(".empty-state h3")).toHaveText("沒有符合條件的商品")
  })

  test("套用單一規格篩選 CPU核數≥8：結果集合正確", async ({ page }) => {
    await gotoListing(page)
    const oracle = applyConditions(ITEMS, [{ field: "cores", threshold: 8 }])
    expect(oracle.length).toBeGreaterThan(0)

    await applyFilter(page, "cores", 8)

    await expect(page.locator(".cond-chips .fchip", { hasText: "CPU核數≥8" })).toBeVisible()
    await expect(page.locator(".pl-count b")).toHaveText(String(oracle.length))
    expect(await renderedNames(page)).toEqual(sortedNames(oracle))
  })

  test("多條件 AND：VRAM≥12G 且 瓦數≥750W → 空狀態（wattage_w 資料缺口）", async ({ page }) => {
    await gotoListing(page)
    const oracle = applyConditions(ITEMS, [
      { field: "vram_gb", threshold: 12 },
      { field: "wattage_w", threshold: 750 },
    ])
    expect(oracle.length).toBe(0)

    await applyFilter(page, "vram_gb", 12)
    await applyFilter(page, "wattage_w", 750)

    await expect(page.locator(".cond-chips .fchip", { hasText: "VRAM≥12G" })).toBeVisible()
    await expect(page.locator(".cond-chips .fchip", { hasText: "瓦數≥750W" })).toBeVisible()
    await expect(page.locator(".pl-count b")).toHaveText("0")
    await expect(page.locator(".empty-state h3")).toHaveText("沒有符合條件的商品")
    // 空狀態列出已套用的兩個條件
    await expect(page.locator(".empty-conds .fchip")).toHaveCount(2)
  })

  test("多條件 AND（非平凡交集）：CPU核數≥8 且 TDP≥120W → 交集正確", async ({ page }) => {
    await gotoListing(page)
    const oracle = applyConditions(ITEMS, [
      { field: "cores", threshold: 8 },
      { field: "tdp_w", threshold: 120 },
    ])
    expect(oracle.length).toBeGreaterThan(0)

    await applyFilter(page, "cores", 8)
    await applyFilter(page, "tdp_w", 120)

    await expect(page.locator(".cond-chips .fchip", { hasText: "CPU核數≥8" })).toBeVisible()
    await expect(page.locator(".cond-chips .fchip", { hasText: "TDP≥120W" })).toBeVisible()
    await expect(page.locator(".pl-count b")).toHaveText(String(oracle.length))
    expect(await renderedNames(page)).toEqual(sortedNames(oracle))
  })

  test("搜尋與篩選同時作用：搜尋「RTX 5070」＋ VRAM≥12G", async ({ page }) => {
    await gotoListing(page)
    const keyword = "RTX 5070"
    const kwHits = ITEMS.filter(it => matchesKeyword(it, keyword))
    expect(kwHits.length).toBeGreaterThan(0)
    const oracle = filterByKeywordAndConditions(ITEMS, keyword, [{ field: "vram_gb", threshold: 12 }])
    expect(oracle.length).toBeGreaterThan(0)

    await search(page, keyword)
    await expect(page.locator(".pl-count b")).toHaveText(String(kwHits.length))

    await applyFilter(page, "vram_gb", 12)
    await expect(page.locator(".cond-chips .fchip", { hasText: "VRAM≥12G" })).toBeVisible()
    await expect(page.locator(".pl-count b")).toHaveText(String(oracle.length))
    expect(await renderedNames(page)).toEqual(sortedNames(oracle))
  })

  test("清除全部條件：回到完整集合（搜尋框清空＋條件 chips 移除）", async ({ page }) => {
    await gotoListing(page)

    await search(page, "RTX 5070")
    await expect(page.locator(".pl-count b")).toHaveText(String(ITEMS.filter(it => matchesKeyword(it, "RTX 5070")).length))
    await applyFilter(page, "vram_gb", 12)
    await expect(page.locator(".cond-chips .fchip")).toHaveCount(1)

    await page.getByRole("button", { name: "清除全部條件" }).click()

    await expect(page.locator(".pl-count b")).toHaveText(String(TOTAL))
    await expect(page.locator("input.search-input")).toHaveValue("")
    await expect(page.locator(".cond-chips .fchip")).toHaveCount(0)
    await expect(page.locator(".pl-clear")).toHaveCount(0) // 條件清除後「清除全部」按鈕隱藏
  })

  test("篩選組合無結果：VRAM≥24G 且 瓦數≥1200W → 空狀態＋可清除", async ({ page }) => {
    await gotoListing(page)
    const oracle = applyConditions(ITEMS, [
      { field: "vram_gb", threshold: 24 },
      { field: "wattage_w", threshold: 1200 },
    ])
    expect(oracle.length).toBe(0)

    await applyFilter(page, "vram_gb", 24)
    await applyFilter(page, "wattage_w", 1200)

    await expect(page.locator(".empty-state h3")).toHaveText("沒有符合條件的商品")
    await expect(page.locator(".empty-conds .fchip")).toHaveCount(2)
    await expect(page.locator(".empty-state")).toContainText("VRAM≥24G")
    await expect(page.locator(".empty-state")).toContainText("瓦數≥1200W")

    // 空狀態的「清除篩選」應可清除條件並回到完整集合
    await page.getByRole("button", { name: "清除篩選" }).click()
    await expect(page.locator(".pl-count b")).toHaveText(String(TOTAL))
    await expect(page.locator(".cond-chips .fchip")).toHaveCount(0)
  })

  test("邊界值納入（≥ 語意）：vram 恰等於 12G 的商品命中 VRAM≥12G", async ({ page }) => {
    await gotoListing(page)
    const boundaryItems = ITEMS.filter(it => flatSpec(it.spec).vram_gb === 12)
    expect(boundaryItems.length).toBeGreaterThan(0)
    const sample = boundaryItems[0]

    await applyFilter(page, "vram_gb", 12)

    // 恰等於門檻的商品必須出現在結果（>= 語意，邊界納入）
    await expect(
      page.locator(".product-list").getByText(sample.name, { exact: true }),
    ).toBeVisible()
  })

  test("無規格欄位商品被結構化篩選靜默排除、頁面不報錯", async ({ page }) => {
    const pageErrors: string[] = []
    page.on("pageerror", err => pageErrors.push(String(err)))

    await gotoListing(page)
    const oracle = applyConditions(ITEMS, [{ field: "vram_gb", threshold: 12 }])
    expect(oracle.length).toBeGreaterThan(0)

    // 挑一個不具 vram_gb 欄位的商品（如 CPU），驗證其被靜默排除
    const withoutVram = ITEMS.find(it => typeof flatSpec(it.spec).vram_gb !== "number")
    expect(withoutVram).toBeTruthy()

    await applyFilter(page, "vram_gb", 12)

    await expect(page.locator(".pl-count b")).toHaveText(String(oracle.length))
    await expect(page.locator(".product-list").getByText(withoutVram!.name, { exact: true })).toHaveCount(0)
    // 頁面不報錯：無 spec 錯誤提示、無資料載入/格式錯誤、無空狀態（因結果非空）
    await expect(page.locator(".spec-err")).toHaveCount(0)
    await expect(page.locator(".empty-state")).toHaveCount(0)
    await expect(page.locator("text=資料載入失敗")).toHaveCount(0)
    await expect(page.locator("text=資料格式錯誤")).toHaveCount(0)
    expect(pageErrors).toEqual([])
  })
})

test.describe("003 記憶體篩選回歸（ram_gb vs capacity）", () => {
  test("搜尋記憶體商品名稱命中（16GB/GB/DDR5）；「>1GB」為 literal 空結果", async ({ page }) => {
    await gotoListing(page)
    const ramItems = ITEMS.filter(it => it.category === "記憶體")
    expect(ramItems.length).toBeGreaterThan(0)

    // 記憶體商品名稱命中（oracle 動態計算，不寫死漂移筆數）
    for (const kw of ["16GB", "GB", "DDR5"]) {
      const hits = ITEMS.filter(it => matchesKeyword(it, kw))
      expect(hits.length).toBeGreaterThan(0)
      await search(page, kw)
      await expect(page.locator(".pl-count b")).toHaveText(String(hits.length))
    }

    // 「>1GB」為 literal 空結果（寫死為預期，防回歸：搜尋只做 name+spec 字面子字串比對）
    expect(ITEMS.filter(it => matchesKeyword(it, ">1GB")).length).toBe(0)
    await search(page, ">1GB")
    await expect(page.locator(".pl-count b")).toHaveText("0")
    await expect(page.locator(".empty-state h3")).toHaveText("沒有符合「>1GB」的商品")
  })

  test("規格篩選 記憶體≥16GB（ram_gb）：結果集合正確且不含 SSD/HDD", async ({ page }) => {
    await gotoListing(page)
    const oracle = applyConditions(ITEMS, [{ field: "ram_gb", threshold: 16 }])
    expect(oracle.length).toBeGreaterThan(0)

    // 防回歸：記憶體（ram_gb）篩選結果不得含任何 SSD/HDD 商品
    const storageNames = new Set(
      ITEMS.filter(it => it.category === "SSD" || it.category === "HDD").map(it => it.name),
    )
    expect(oracle.filter(it => storageNames.has(it.name))).toEqual([])

    await applyFilter(page, "ram_gb", 16)
    await expect(page.locator(".cond-chips .fchip", { hasText: "記憶體≥16GB" })).toBeVisible()
    await expect(page.locator(".pl-count b")).toHaveText(String(oracle.length))
    expect(await renderedNames(page)).toEqual(sortedNames(oracle))
  })

  test("規格篩選 記憶體≥32GB（ram_gb）：高門檻動態 oracle", async ({ page }) => {
    await gotoListing(page)
    const oracle = applyConditions(ITEMS, [{ field: "ram_gb", threshold: 32 }])
    expect(oracle.length).toBeGreaterThan(0)

    await applyFilter(page, "ram_gb", 32)
    await expect(page.locator(".cond-chips .fchip", { hasText: "記憶體≥32GB" })).toBeVisible()
    await expect(page.locator(".pl-count b")).toHaveText(String(oracle.length))
    expect(await renderedNames(page)).toEqual(sortedNames(oracle))
  })

})
