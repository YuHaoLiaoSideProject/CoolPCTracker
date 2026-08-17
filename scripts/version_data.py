#!/usr/bin/env python3
"""data/ 異動判定 + api/ 衍生 API 建置（契約 v2：對外層依分類切檔）。

- 輸入：
  - data/meta.json：crawled_at / source / counts / total / status（唯一 meta）
  - data/items/{g}.json：每分類一檔（純 items 陣列、無 category 欄位、無 meta）
    —— 爬蟲真相層（crawler 寫入；g 由檔名繼承）
  - data/daily/YYYYMMDD.json：每日價格點 {"<item_id>": <price>, ...}（歷史真相序列）
  - 遷移相容：若 data/items.json（舊單檔 {"meta","items"}，items 含 category 欄位）
    仍在但 data/items/ 不存在 → 依 category 欄位拆出寫入 data/items/{g}.json
    （一條相容路徑，方便遷移；印警告至 stderr）。寫入後即以分類檔為真相。

- 輸出（僅異動時寫，見「changed 判定」）：
  - api/items/{g}.json：鏡像 data/items/{g}.json —— 同內容、compact；
    g 由檔名繼承（分類檔名即對外 id）
  - api/daily/{同 data/daily 檔名}.json：鏡像 data/daily（byte 一致，有新增/更新才寫）
  - api/trends/{item_id}.json = {"id": ..., "history": [[d, p], ...]}：
    逐商品全歷史，依日期升冪，由所有 data/daily 檔聚合
    （每個 daily 檔的 {id: price} 併入對應 item 的 history；每次全量重建以保持冪等）
  - api/index.json = {generated_at, source, description, categories[],
    crawled_at, status, total, counts, daily_files[], trends_prefix}（目錄入口）
    categories = [{id: g, name, file: "api/items/{g}.json", count}]；id=g（檔名繼承），
    name 由本檔 G→name 唯讀對照解析（依 crawler/categories.py 之 g_index→name
    寫死一份於此，供 index 使用；若 data/items 檔名非已知 G 索引 → 以檔名本身為 name）
  - 不再產生單一 api/latest.json（由 api/items/{g} 取代）；
    index 不再含 latest_file / latest 欄位（前端以 categories[] + crawled_at 組 URL）。
- 防線：meta.status == "failed" 或 meta.total == 0 → 判定 changed=false，不寫任何
  檔案（含 items/daily/trends/index；遷移拆檔也不執行），並輸出明確訊息（健康
  檢查延伸到衍生層，防人工手術壞資料覆寫既有對外成品）。
- changed 判定：① data/daily 有 api/daily 缺的新檔 ② 任一 data/items/{g}.json 與
  對應 api/items/{g}.json items 有異動（canonical 比較，僅 items payload；缺檔視為
  異動；crawled_at 不參與，避免時間戳造成永遠「有異動」）；無異動 → 不寫任何檔案。
- 輸出：stdout 印 changed=true|false 與 filename（最新 daily 檔名或空）；
  若環境變數 GITHUB_OUTPUT 存在（GitHub Actions），以 key=value 追加寫入，供
  crawl.yml steps.version.outputs.changed / outputs.filename 使用

職責分層：data/ 是 crawler 唯一真相（items/{g} 分類檔 + daily/ 歷史點序列 +
meta.json），api/ 是本模組產出的對外 API 面（items/{g} + daily 鏡像 + trends +
index.json）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOURCE_URL = "https://www.coolpc.com.tw/m/m-list.php"
DESCRIPTION = "原價屋商品價格追蹤資料 API"

# G → 分類中文名 唯讀對照（依 crawler/categories.py 的 CATEGORIES g_index→name 寫死
# 一份於本檔；data/items 檔名只帶 g（G 索引）時，index.categories[].name 由此解析）。
# 更新 crawler 白名單時需同步此表（crawler/categories.py 仍是單一事實來源）。
G_NAME_MAP: dict[str, str] = {
    "1": "套裝/準系統",
    "3": "劈發價組合區",
    "4": "CPU",
    "5": "主機板",
    "6": "記憶體",
    "7": "SSD",
    "8": "HDD",
    "9": "記憶卡",
    "12": "顯示卡",
}
NAME_TO_G: dict[str, str] = {name: g for g, name in G_NAME_MAP.items()}


def canonical(obj: Any) -> str:
    """canonical JSON：dict key 排序 + 不跳脫非 ASCII（僅供比較，無關寫檔格式）。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def _write_github_output(changed: bool, filename: str | None) -> None:
    """若 GITHUB_OUTPUT 存在（GitHub Actions），以 key=value 追加寫入兩行。

    與工作流 `id: version` step 的 `steps.version.outputs.changed` /
    `outputs.filename` 對應；檔案不存在時由 open("a") 建立。"""
    out_path = os.environ.get("GITHUB_OUTPUT")
    if not out_path:
        return
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(f"changed={'true' if changed else 'false'}\n")
        f.write(f"filename={filename or ''}\n")


# ── data/ 讀取 ─────────────────────────────────────────────────────────────

def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _daily_paths(data_dir: Path) -> list[Path]:
    """掃 data/daily/*.json（只認 YYYYMMDD.json 檔名），依檔名升冪排序。

    非 8 位數字檔名的殘留檔忽略（不參與鏡像/聚合/索引）。"""
    daily_dir = data_dir / "daily"
    if not daily_dir.is_dir():
        return []
    entries: list[tuple[str, Path]] = []
    for p in daily_dir.glob("*.json"):
        stem = p.stem
        if len(stem) == 8 and stem.isdigit():
            entries.append((stem, p))
    entries.sort(key=lambda e: e[0])  # 檔名升冪 = 日期升冪
    return [p for _, p in entries]


def _daily_date(stem: str) -> str:
    """YYYYMMDD → YYYY-MM-DD（與 items history 點格式一致）。"""
    return f"{stem[0:4]}-{stem[4:6]}-{stem[6:8]}"


def _read_daily_prices(path: Path) -> dict | None:
    """讀每日價格點 {id: price}；解析失敗或非 object → None（視為壞檔跳過）。"""
    try:
        payload = _load_json(path)
    except (ValueError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _daily_records(data_dir: Path) -> list[tuple[Path, int]]:
    """data/daily/*.json → [(path, records)]（依檔名升冪）；壞檔（不可解析）跳過。"""
    out: list[tuple[Path, int]] = []
    for path in _daily_paths(data_dir):
        prices = _read_daily_prices(path)
        if prices is not None:
            out.append((path, len(prices)))
    return out


def _nat_key(stem: str) -> tuple[int, int | str]:
    """自然排序鍵：純數字 stem（G 索引）依數值排序，其餘依字串排序。"""
    return (0, int(stem)) if stem.isdigit() else (1, stem)


def _items_paths(data_dir: Path) -> list[Path]:
    """掃 data/items/*.json（g = 檔名 stem），依自然序（G 索引數值序）排序。

    data/items/ 不存在（尚未遷移或爬蟲未產出分類檔）→ 空。"""
    items_dir = data_dir / "items"
    if not items_dir.is_dir():
        return []
    return sorted(items_dir.glob("*.json"), key=lambda p: _nat_key(p.stem))


def _read_items_file(path: Path) -> list | None:
    """讀單分類 items 陣列；解析失敗或非 list → None（視為壞檔跳過）。"""
    try:
        payload = _load_json(path)
    except (ValueError, OSError):
        return None
    return payload if isinstance(payload, list) else None


def _resolve_category(stem: str) -> tuple[str, str]:
    """檔名 stem → (g, name)。

    g = 檔名原樣（對外 id 由檔名繼承）；name 優先取 G→name 對照（stem 為純 G 索引
    或 g-開頭複合名時以對應中文名）→ 查無則以檔名本身為 name。"""
    head = re.split(r"[-_]", stem, maxsplit=1)[0]
    if head in G_NAME_MAP:
        return stem, G_NAME_MAP[head]
    return stem, stem


def _categories(data_dir: Path) -> list[tuple[str, str, list]]:
    """data/items/*.json → [(g, name, items)]（依檔名自然序）；壞檔（不可解析）跳過。"""
    out: list[tuple[str, str, list]] = []
    for path in _items_paths(data_dir):
        items = _read_items_file(path)
        if items is None:
            continue
        g, name = _resolve_category(path.stem)
        out.append((g, name, items))
    return out


def _safe_g(name: str) -> str:
    """檔名安全化：path 不友好字元（/ : …）以 "-" 取代；空結果 → "unknown"。

    僅遷移路徑用（舊單檔含未列於 G→name 對照的分類名時產生 g）。"""
    g = re.sub(r'[\\/:*?"<>|]+', "-", name).strip()
    return g or "unknown"


def _migrate_legacy_single_file(data_dir: Path) -> None:
    """遷移相容路徑：data/items.json（舊單檔，items 含 category 欄位）仍在且
    data/items/ 不存在 → 依 category 拆出寫入 data/items/{g}.json（純 items 陣列、
    移除 category 欄位、無 meta），並印警告至 stderr。寫入後本目錄即轉為分類檔
    真相層，下次執行不再走此路徑。分類名在 G→name 對照內 → g 用 G 索引；
    否則以檔名安全化字串為 g。"""
    items_path = data_dir / "items.json"
    if (data_dir / "items").is_dir() or not items_path.exists():
        return
    doc = _load_json(items_path)
    entries = doc.get("items", []) if isinstance(doc, dict) else []
    by_category: dict[str, list] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        category = str(entry.get("category") or "未分類")
        by_category.setdefault(category, []).append(
            {k: v for k, v in entry.items() if k != "category"})
    items_dir = data_dir / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    for category, payload in sorted(by_category.items()):
        g = NAME_TO_G.get(category) or _safe_g(category)
        (items_dir / f"{g}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
    print(f"[version_data] 警告：data/items.json（舊單檔）仍在但 data/items/ 不存在，"
          f"已依 category 欄位拆出 {len(by_category)} 個分類檔寫入 data/items/"
          "（遷移相容路徑）。", file=sys.stderr)


# ── api/ 組裝 ──────────────────────────────────────────────────────────────

def build_trends(data_dir: Path) -> dict[str, list[list]]:
    """聚合所有 data/daily 檔 → {item_id: [[d, p], ...]}（依日期升冪）。

    每個 daily 檔的 {id: price} 併入對應 item 的 history；檔序即日期序，
    逐檔 append 即得升冪序列。同檔重複鍵（JSON 不可能）防禦去重。"""
    trends: dict[str, list[list]] = {}
    for path in _daily_paths(data_dir):
        date_str = _daily_date(path.stem)
        prices = _read_daily_prices(path)
        if prices is None:
            continue
        for iid, price in prices.items():
            key = str(iid)
            bucket = trends.setdefault(key, [])
            if not bucket or bucket[-1][0] != date_str:
                bucket.append([date_str, price])
    return trends


def write_trends(api_dir: Path, trends: dict[str, list[list]]) -> None:
    """全量重建 api/trends/{item_id}.json（冪等：同輸入 → 同輸出）。

    僅寫入聚合結果；無任何價格點 → 不建立 api/trends/。"""
    if not trends:
        return
    trends_dir = api_dir / "trends"
    trends_dir.mkdir(parents=True, exist_ok=True)
    for iid, history in trends.items():
        payload = {"id": iid, "history": history}
        (trends_dir / f"{iid}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")


def mirror_daily(data_dir: Path, api_dir: Path) -> None:
    """鏡像 data/daily → api/daily（byte 一致；僅寫新增或內容不同的檔）。"""
    for path in _daily_paths(data_dir):
        dest = api_dir / "daily" / path.name
        if dest.exists() and dest.read_bytes() == path.read_bytes():
            continue  # 已是最新 → 不寫（無新增/更新）
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)


def items_changed(api_dir: Path, categories: list[tuple[str, str, list]]) -> bool:
    """任一 data/items/{g}.json 與對應 api/items/{g}.json 有異動（canonical 比較）。

    缺檔（首次執行或新增分類）視為異動；對應檔不可解析 → 視為異動（重寫）。"""
    for g, _name, items in categories:
        path = api_dir / "items" / f"{g}.json"
        if not path.exists():
            return True
        try:
            existing = _load_json(path)
        except (ValueError, OSError):
            return True
        if canonical(items) != canonical(existing):
            return True
    return False


def write_items(api_dir: Path, categories: list[tuple[str, str, list]]) -> None:
    """鏡像 api/items/{g}.json：同 data/items/{g} 內容、compact 寫出；
    僅寫新增或內容不同的檔（已是最新 → 不寫）。"""
    for g, _name, items in categories:
        dest = api_dir / "items" / f"{g}.json"
        text = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
        if dest.exists() and dest.read_text(encoding="utf-8") == text:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")


def build_index(data_dir: Path, meta: dict,
                categories: list[tuple[str, str, list]]) -> dict:
    """組裝 api/index.json：categories[] 由 data/items/ 分類檔組成（id=g、name 依
    G→name 對照、file=api/items/{g}.json、count=該檔 items 數量）；daily_files[]
    掃 data/daily（依檔名升冪，含 records 計數）；trends_prefix 指標。
    不再含 latest_file/latest（前端以 categories[] + crawled_at 組 URL）。"""
    daily_files = [
        {"file": path.name, "url": f"api/daily/{path.name}", "records": records}
        for path, records in _daily_records(data_dir)
    ]
    cat_meta = [
        {"id": g, "name": name, "file": f"api/items/{g}.json", "count": len(items)}
        for g, name, items in categories
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": meta.get("source", SOURCE_URL),
        "description": DESCRIPTION,
        "crawled_at": meta.get("crawled_at"),
        "status": meta.get("status"),
        "total": meta.get("total"),
        "counts": meta.get("counts", {}),
        "categories": cat_meta,
        "daily_files": daily_files,
        "trends_prefix": "api/trends/",
    }


def write_index(api_dir: Path, data_dir: Path, meta: dict,
                categories: list[tuple[str, str, list]]) -> None:
    """寫 api/index.json（indent=2）。"""
    index = build_index(data_dir, meta, categories)
    (api_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：python scripts/version_data.py [--data-dir data] [--api-dir api]（回傳 0）。

    流程：
    1. 讀 data/meta.json
    2. 防線：meta.status == "failed" 或 meta.total == 0 → changed=false，
       不寫任何檔案（含遷移拆檔），直接輸出
    3. 遷移相容：data/items.json 仍在且 data/items/ 不存在 → 依 category 拆出寫入
    4. 讀 data/items/{g}.json（依檔名自然序）與 data/daily/*.json
    5. changed 判定：data/daily 有 api/daily 缺的新檔，或任一分類檔與
       api/items/{g}.json canonical 不同（缺檔視為異動）
    6. 有異動 → 依序寫 api/items/{g}（compact 鏡像）→ 鏡像 api/daily →
       全量重建 api/trends/ → 重建 api/index.json（含 categories[]）
    7. 無異動 → 不動任何檔案
    8. stdout 輸出 changed / filename（最新 daily 檔名或空），並依 GITHUB_OUTPUT 追加寫入。
    """
    arg_parser = argparse.ArgumentParser(prog="version_data")
    arg_parser.add_argument("--data-dir", default="data", type=Path)
    arg_parser.add_argument("--api-dir", default="api", type=Path)
    args = arg_parser.parse_args(argv)
    data_dir: Path = args.data_dir
    api_dir: Path = args.api_dir

    meta = _load_json(data_dir / "meta.json")

    # 防線：crawler 健康檢查（failed / total==0）延伸到衍生層 —— 人工手術或
    # 壞資料不得覆寫既有對外成品：判定 changed=false，不寫任何檔案（遷移也不做）。
    if meta.get("status") == "failed" or meta.get("total") == 0:
        print("changed=false")
        print("filename=")
        _write_github_output(False, None)
        return 0

    # 遷移相容：舊單檔 → 依 category 拆出 data/items/{g}.json（印警告）
    if not (data_dir / "items").is_dir() and (data_dir / "items.json").exists():
        _migrate_legacy_single_file(data_dir)
    categories = _categories(data_dir)

    daily_paths = _daily_paths(data_dir)
    filename = daily_paths[-1].name if daily_paths else ""  # 最新 daily 檔名或空

    # changed 判定：① data/daily 有新檔（api/daily 無對應檔名）
    #              ② 任一分類檔與 api/items/{g}.json 有異動（canonical）
    new_daily = [p for p in daily_paths if not (api_dir / "daily" / p.name).exists()]
    changed = bool(new_daily) or items_changed(api_dir, categories)

    if changed:
        api_dir.mkdir(parents=True, exist_ok=True)
        # 1) api/items/{g}.json：鏡像 data/items/{g}（同內容、compact；g 由檔名繼承）
        write_items(api_dir, categories)
        # 2) api/daily：鏡像 data/daily（有新增/更新才寫）
        mirror_daily(data_dir, api_dir)
        # 3) api/trends：全量重建（聚合所有 daily 檔，冪等）
        write_trends(api_dir, build_trends(data_dir))
        # 4) api/index.json：目錄入口（categories[] + daily_files[] + trends_prefix；
        #    不再含 latest/latest_file）
        write_index(api_dir, data_dir, meta, categories)

    print(f"changed={'true' if changed else 'false'}")
    print(f"filename={filename or ''}")
    _write_github_output(changed, filename)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())