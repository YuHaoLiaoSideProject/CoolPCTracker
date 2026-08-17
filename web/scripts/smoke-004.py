#!/usr/bin/env python3
"""004 真資料 smoke test（playwright）— 以 api/ 分類檔聚合為期望值驗證前端（契約 v2）。

前置：`npm run build` 後 `npx vite preview`（build 收尾把 ../api/** 複製進 dist/api/）。

驗證（真資料，期望值由資料動態計算，不硬編碼）：
1. 列表載入（v2 以 ?category=all 進入「全部」視圖）：全部商品卡片 = 全分類 items 聚合數；
   側欄分類計數與真資料逐項一致
2. 點分類（CPU）／回全部
3. 搜尋「RTX 5060」（以 search.ts 相同語意計算期望值：name + spec 平鋪值 lowercase 子字串）
4. 規格篩選 VRAM≥12G → 清除
5. 詳情頁（真 GPU deep link）：目前價／首日追蹤／歷史最低／規格表／價格趨勢圖 canvas／目標價 markLine 流程
6. 邊界：無效 id → 找不到此商品；console/pageerror 無錯誤
期望值一律由 api/index.json（v2：categories[] 目錄 + crawled_at；**無 latest_file**）→
逐一載入 api/items/{file}（純陣列）聚合計算；前端以 `?v={crawled_at}` 快取穿透
（鏡像 useItems.itemFileUrl），不硬編碼。
"""
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

WEB_ROOT = Path(__file__).resolve().parent.parent  # web/
REPO_ROOT = WEB_ROOT.parent
BASE = "http://localhost:4173/CoolPCTracker/"  # vite preview 預設綁定 ::1（IPv6 localhost）
failures = []


def check(name, cond, extra=""):
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name}" + (f" — {extra}" if extra and not cond else ""))
    if not cond:
        failures.append(name)


# ── 期望值：讀 api/index.json（categories[] + crawled_at）→ 逐一載入分類檔聚合 ──
#    （與 vite build 複製進 dist/api/ 同一批檔案；前端以 ?v=crawled_at 快取穿透）
def load_real_data():
    """回傳 (categories, crawled_at, items)；items 為全部分類聚合（每筆依分類檔 stamp category）。"""
    index = json.loads((REPO_ROOT / "api" / "index.json").read_text(encoding="utf-8"))
    categories = index["categories"]
    crawled_at = index["crawled_at"]
    assert categories and crawled_at, "index.json 應含 categories[] 與 crawled_at（v2 契約；不再有 latest_file）"
    items = []
    for cat in categories:
        file = cat["file"]
        # 相容全路徑（api/items/4.json）與單檔名（4.json）兩種寫法
        rel = file[len("api/items/"):] if file.startswith("api/items/") else file
        raw = json.loads((REPO_ROOT / "api" / "items" / rel).read_text(encoding="utf-8"))
        assert isinstance(raw, list), f"{file} 應為純陣列（v2 分類檔）"
        for it in raw:
            it = dict(it)
            it.setdefault("category", cat["name"])  # v2 Item 無 category → 依分類檔 stamp
            items.append(it)
    return categories, crawled_at, items


def flatten_spec(spec):
    """鏡像 useItems.normalizeSpec：extra 平鋪 + null/空值剔除。"""
    out = {}
    src = spec if isinstance(spec, dict) else {}
    extra = src.get("extra")
    for k, v in src.items():
        if v is None or v == "":
            continue
        out[k] = v
    if isinstance(extra, dict):
        for k, v in extra.items():
            if v is None or v == "":
                continue
            out[k] = v
    out.pop("extra", None)
    return out


def match_keyword(it, q):
    """鏡像 search.ts matchesKeyword：name + spec 平鋪值 lowercase 子字串。"""
    if q in it["name"].lower():
        return True
    spec_text = " ".join(str(v) for v in flatten_spec(it.get("spec", {})).values()).lower()
    return q in spec_text


def main():
    categories, crawled_at, items = load_real_data()
    total = len(items)
    counts = {}
    for it in items:
        counts[it["category"]] = counts.get(it["category"], 0) + 1
    cpu_id = next(c["id"] for c in categories if c["name"] == "CPU")

    # 搜尋期望值（與前端同語意）
    q_rtx = "rtx 5060"
    exp_rtx = [it for it in items if match_keyword(it, q_rtx)]
    # VRAM≥12G 期望值（specFilter ≥ 語意：spec.vram_gb number >= 12）
    exp_vram = [it for it in items
                if isinstance(flatten_spec(it.get("spec", {})).get("vram_gb"), (int, float))
                and flatten_spec(it.get("spec", {})).get("vram_gb") >= 12]
    # 詳情頁真商品：找一筆 VRAM 12G、chip 已解析的 RTX 3060
    gpu_detail = None
    for it in items:
        spec = flatten_spec(it.get("spec", {}))
        if it["category"] == "顯示卡" and spec.get("chip") == "RTX 3060" and spec.get("vram_gb") == 12:
            gpu_detail = it
            break
    assert gpu_detail is not None, "找不到 RTX 3060 12G 真商品"

    print(f"=== 真資料期望值：categories={len(categories)} ?v={crawled_at[:19]} total={total} "
          f"搜尋「{q_rtx}」={len(exp_rtx)} VRAM≥12G={len(exp_vram)} 詳情={gpu_detail['name'][:30]}…")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        # ── 1. 列表載入（?category=all 全部視圖）：全部分類卡片 + 側欄分類計數 ──
        t0 = time.time()
        page.goto(BASE + "#/?category=all", wait_until="networkidle")
        page.wait_for_function(
            f"document.querySelectorAll('.product-card').length === {total}",
            timeout=15000,
        )
        check(f"全部商品卡片 = {total}", page.locator(".product-card").count() == total,
              f"got {page.locator('.product-card').count()}")
        print(f"      （首屏 {total} 卡片渲染耗時 {time.time() - t0:.1f}s）")

        # 側欄分類計數逐項比對（v2 側欄數值取自 index counts，與分類檔聚合一致）
        for cat, exp in counts.items():
            el = page.locator(".sidebar .cat", has_text=cat)
            cnt = el.locator(".cat-cnt").inner_text().strip()
            check(f"側欄 {cat} 計數 = {exp}", cnt == str(exp), f"got {cnt}")
        all_cnt = page.locator(".sidebar .cat", has_text="全部").locator(".cat-cnt").inner_text().strip()
        check(f"側欄 全部 計數 = {total}", all_cnt == str(total), f"got {all_cnt}")

        # ── 2. 點分類 CPU（v2 URL 帶分類 id，如 ?category=4）→ 回全部 ──
        page.locator(".sidebar .cat", has_text="CPU").click()
        page.wait_for_url(re.compile(rf"category={re.escape(cpu_id)}(?:&|$)"))
        page.wait_for_function(
            f"document.querySelectorAll('.product-card').length === {counts['CPU']}",
            timeout=10000,
        )
        check(f"點 CPU → URL category={cpu_id}", f"category={cpu_id}" in page.url, page.url)
        check(f"CPU 分類卡片 = {counts['CPU']}", page.locator(".product-card").count() == counts["CPU"],
              f"got {page.locator('.product-card').count()}")
        page.locator(".sidebar .cat", has_text="全部").click()
        page.wait_for_url(re.compile(r"category=all"))
        page.wait_for_function(
            f"document.querySelectorAll('.product-card').length === {total}",
            timeout=15000,
        )
        check(f"回全部 → 卡片 = {total}", page.locator(".product-card").count() == total)

        # ── 3. 搜尋 RTX 5060（非空關鍵字 → 自動切至全部視圖 + loadAll 跨分類） ──
        page.locator(".search-input").fill("RTX 5060")
        page.wait_for_function(
            f"document.querySelectorAll('.product-card').length === {len(exp_rtx)}",
            timeout=10000,
        )
        check(f"搜尋「RTX 5060」→ {len(exp_rtx)} 筆", page.locator(".product-card").count() == len(exp_rtx))
        names = [page.locator(".pc-name").nth(i).inner_text().lower() for i in range(len(exp_rtx))]
        chips = [page.locator(".pc-specs").nth(i).inner_text().lower() for i in range(len(exp_rtx))]
        # 搜尋語意 = name 或 spec（spec 平鋪值）；RTX5060（無空格）商品經規格 chip "RTX 5060" 命中
        miss = [n for n, c in zip(names, chips) if "rtx 5060" not in n and "rtx 5060" not in c]
        check("命中卡片皆含 rtx 5060（名稱或規格 chip）", not miss, f"miss: {miss[:3]}")
        page.locator(".search-input").fill("")
        page.wait_for_function(f"document.querySelectorAll('.product-card').length === {total}")

        # ── 4. 規格篩選 VRAM≥12G → 清除全部條件 ──
        page.locator('select[aria-label="規格欄位"]').select_option("vram_gb")
        page.locator(".spec-value").fill("12")
        page.locator(".spec-form .btn-primary").click()
        page.wait_for_function(
            f"document.querySelectorAll('.product-card').length === {len(exp_vram)}",
            timeout=10000,
        )
        check(f"VRAM≥12G → {len(exp_vram)} 筆", page.locator(".product-card").count() == len(exp_vram),
              f"got {page.locator('.product-card').count()}")
        page.locator(".pl-clear").click()
        page.wait_for_function(f"document.querySelectorAll('.product-card').length === {total}")
        check(f"清除全部條件 → 回 {total}", page.locator(".product-card").count() == total)

        # ── 5. 詳情頁（真 GPU deep link）：目前價／首日追蹤／歷史最低／規格／圖表／目標價 ──
        page.goto(BASE + f"#/product/{gpu_detail['id']}", wait_until="networkidle")
        title = page.locator(".detail-title").first.inner_text().strip()
        check("詳情標題顯示商品名", title == gpu_detail["name"], f"{title[:50]} vs {gpu_detail['name'][:50]}")
        cur = page.locator(".price-current").inner_text()
        check("目前價格顯示 NT$", "NT$" in cur, cur)
        chg = page.locator(".price-change").inner_text()
        check("單筆歷史 → 首日追蹤標籤", "首日追蹤" in chg, chg)
        check("歷史最低顯示", "歷史最低" in page.locator(".price-summary").inner_text())
        low = page.locator(".price-low").inner_text()
        check("歷史最低金額", "NT$" in low, low)
        check("規格表渲染（品牌/晶片/VRAM…）", page.locator(".spec-key").count() >= 3,
              f"got {page.locator('.spec-key').count()}")
        spec_text = page.locator(".spec-table").inner_text()
        check("規格含晶片 RTX 3060", "RTX 3060" in spec_text, spec_text[:80])
        check("規格含 VRAM 12", "12" in spec_text, "")
        check("價格趨勢圖 canvas 渲染（lightweight-charts）", page.locator(".price-trend-chart canvas").count() >= 1)

        # 目標價 markLine 流程：9500 套用 → 修改 9800 → abc 錯誤 → 清除
        page.locator(".target-input").fill("9500")
        page.locator(".target-btn", has_text="設定目標價").click()
        check("套用後出現清除按鈕（markLine 生效）", page.locator(".target-btn.ghost", has_text="清除目標價").is_visible())
        check("無驗證錯誤", page.locator(".target-error").inner_text() == "")
        page.locator(".target-input").fill("abc")
        page.locator(".target-btn", has_text="設定目標價").click()
        check("abc → 請輸入有效數字", page.locator(".target-error").inner_text() == "請輸入有效數字",
              page.locator(".target-error").inner_text())
        check("abc → 紅框 is-error", "is-error" in (page.locator(".target-input").get_attribute("class") or ""))
        page.locator(".target-input").fill("9500")
        page.locator(".target-btn", has_text="設定目標價").click()
        page.locator(".target-btn.ghost").click()
        check("清除後按鈕消失", page.locator(".target-btn.ghost").count() == 0)

        # ── 6. 邊界：無效 id → 找不到商品；返回列表保留 context ──
        page.goto(BASE + "#/product/8a4b2c6d1e9f3a71", wait_until="networkidle")
        check("無效 id → 找不到此商品", page.locator(".state-title").inner_text() == "找不到此商品",
              page.locator(".state-title").inner_text())
        page.wait_for_selector(".state-center .back-link")  # not-found 頁返回連結（非 breadcrumb）
        page.locator(".state-center .back-link").click()
        page.wait_for_url(re.compile(r"/$"))
        page.wait_for_function("document.querySelectorAll('.product-card').length >= 1", timeout=15000)
        check("返回列表", page.locator(".product-card").count() >= 1)

        # ── 7. console / pageerror（favicon 404 除外） ──
        real_errors = [e for e in errors if "favicon" not in e]
        check("console 無 error", len(real_errors) == 0, "; ".join(real_errors[:3]))

        browser.close()

    print(f"\n=== smoke（?v={crawled_at[:10]}）: {len(failures)} failed / total 30 ===")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()