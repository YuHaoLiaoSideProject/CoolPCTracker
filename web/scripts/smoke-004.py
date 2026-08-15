#!/usr/bin/env python3
"""004 smoke test — 列表→詳情→目標價 markLine→修改/清除→無效輸入→返回列表（playwright）"""
import re
import sys
from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:4173/CoolPCTracker/"
failures = []


def check(name, cond, extra=""):
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name}" + (f" — {extra}" if extra and not cond else ""))
    if not cond:
        failures.append(name)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    # ── 1. 列表載入 → 點商品卡進詳情 ──
    page.goto(BASE, wait_until="networkidle")
    check("列表載入（卡片可見）", page.locator(".product-card").count() >= 5)
    first_name = page.locator(".product-card .pc-name").first.inner_text()
    page.locator(".product-card").first.click()
    page.wait_for_url(re.compile(r"/product/"))
    check("跳轉詳情路由 /product/:id", "/product/" in page.url, page.url)
    check("詳情標題顯示商品名", page.locator(".detail-title").first.inner_text().strip() == first_name, page.locator(".detail-title").first.inner_text())
    check("目前價格顯示", "NT$" in page.locator(".price-current").inner_text(), page.locator(".price-current").inner_text())
    check("漲跌標籤顯示", page.locator(".price-change").count() > 0, "")
    check("歷史最低顯示", "歷史最低" in page.locator(".price-summary").inner_text())
    check("最後更新（台北時間）", "台北時間" in page.locator(".ps-updated").inner_text(), page.locator(".ps-updated").inner_text())
    check("規格表渲染", page.locator(".spec-key").count() >= 1)
    check("ECharts canvas 渲染", page.locator(".price-trend-chart canvas").count() == 1)

    # ── 2. 目標價：套用 9500 → markLine ──
    page.locator(".target-input").fill("9500")
    page.locator(".target-btn", has_text="設定目標價").click()
    check("套用後出現清除按鈕（markLine 生效）", page.locator(".target-btn.ghost", has_text="清除目標價").is_visible())
    check("無驗證錯誤", page.locator(".target-error").inner_text() == "")

    # ── 3. 修改 9800 ──
    page.locator(".target-input").fill("9800")
    page.locator(".target-btn", has_text="設定目標價").click()
    check("修改後仍無錯誤、清除按鈕在", page.locator(".target-error").inner_text() == "" and page.locator(".target-btn.ghost").is_visible())

    # ── 4. 無效輸入 abc → 紅框＋訊息 ──
    page.locator(".target-input").fill("abc")
    page.locator(".target-btn", has_text="設定目標價").click()
    check("abc → 請輸入有效數字", page.locator(".target-error").inner_text() == "請輸入有效數字", page.locator(".target-error").inner_text())
    check("abc → 紅框 is-error", "is-error" in (page.locator(".target-input").get_attribute("class") or ""))

    # ── 5. 清除目標價 ──
    page.locator(".target-input").fill("9500")
    page.locator(".target-btn", has_text="設定目標價").click()
    page.locator(".target-btn.ghost").click()
    check("清除後按鈕消失", page.locator(".target-btn.ghost").count() == 0)

    # ── 6. 返回列表（保留分類 context）──
    page.locator(".detail-breadcrumb a").click()
    page.wait_for_url(re.compile(r"/$"))
    check("返回列表", page.locator(".product-card").count() >= 1)

    # ── 7. deep link 邊界 ──
    # 空 history 商品（威剛 XPG D10）
    page.goto(BASE + "#/product/294375d822588449", wait_until="networkidle")
    check("空 history → 尚無歷史資料", page.locator(".no-history").inner_text() == "尚無歷史資料")
    check("空 history → 目前價 —", page.locator(".price-current").inner_text() == "—")
    # gone 商品（GTX 1650）
    page.goto(BASE + "#/product/7837f9794564236e", wait_until="networkidle")
    check("gone → 下架 badge", page.locator(".badge-gone").inner_text() == "此商品已下架")
    check("gone → 價格照常顯示", "NT$" in page.locator(".price-current").inner_text())
    # 20 點商品 → slider 應渲染（canvas）
    page.goto(BASE + "#/product/5a4b3c2d1e0f9a8b", wait_until="networkidle")
    check("20 點商品圖表渲染", page.locator(".price-trend-chart canvas").count() == 1)
    # 三日同低（Z 特價記憶體）→ 最低日 08-10
    page.goto(BASE + "#/product/1a2b3c4d5e6f7081", wait_until="networkidle")
    low = page.locator(".price-low").inner_text()
    check("三日同低 → 最低 NT$4,500（2026-08-10）", "4,500" in low and "2026-08-10" in low, low)
    # 找不到商品
    page.goto(BASE + "#/product/8a4b2c6d1e9f3a71", wait_until="networkidle")
    check("無效 id → 找不到此商品", page.locator(".state-title").inner_text() == "找不到此商品")

    # ── 8. console / pageerror ──
    real_errors = [e for e in errors if "favicon" not in e]
    check("console 無 error", len(real_errors) == 0, "; ".join(real_errors[:3]))

    browser.close()

print(f"\n=== smoke: {len(failures)} failed / total 20 ===")
sys.exit(1 if failures else 0)
