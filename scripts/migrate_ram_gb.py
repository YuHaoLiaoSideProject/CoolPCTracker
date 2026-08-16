#!/usr/bin/env python3
"""一次性資料遷移：記憶體分類 capacity_gb → ram_gb（根因修正，可重跑、冪等）。

背景（003 記憶體篩選永遠空結果 bug）：
- crawler/spec_parser.py 的 _parse_ram 原本把記憶體容量寫進 extra["capacity_gb"]，
  與 SSD/HDD 的儲存容量共用同一 key；前端下拉「記憶體」綁定 ram_gb → 永遠空結果。
- 修正後 _parse_ram 改寫 extra["ram_gb"]；本腳本對「既有資料」做確定性遷移，
  不重新爬蟲。

遷移規則（僅 category == "記憶體"）：
- spec.extra.capacity_gb → spec.extra.ram_gb（資料檔為巢狀 extra 形狀）
- spec.capacity_gb（若為已正規化的平鋪形狀）→ spec.ram_gb
- 其餘分類（SSD/HDD 的 capacity_gb、記憶卡的 capacity 字串）一律不動

處理檔案（與前端 dev/build 讀取路徑一致）：
- data/items.json（爬蟲產出，indent=2）
- data/items.v2.json、web/public/data/items.v2.json、web/dist/data/items.v2.json
  （compact separators；web/dist/data/ 為 build 產物，此處直接同步，等同重新 build）

用法：
    python scripts/migrate_ram_gb.py [--check]
  --check：僅驗證（dry-run）不寫檔。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

# (路徑, compact 與否)；compact=True 用 separators=(",", ":") 無尾換行，
# 否則 indent=2 且尾端換行（與 crawler 產出 items.json 一致）。
TARGETS: list[tuple[str, bool]] = [
    ("data/items.json", False),
    ("data/items.v2.json", True),
    ("web/public/data/items.v2.json", True),
    ("web/dist/data/items.v2.json", True),
    ("data/items.v1.json", True),  # 舊快照；記憶體為 0 筆，冪等 no-op，一併涵蓋
]


def migrate_item(item: dict[str, Any]) -> bool:
    """就地遷移單一 item；回傳是否變更。僅處理 category == 記憶體。"""
    if item.get("category") != "記憶體":
        return False
    spec = item.get("spec")
    if not isinstance(spec, dict):
        return False
    changed = False

    # 巢狀 extra 形狀（crawler spec_parser 產出 {brand, model, extra:{...}}）
    extra = spec.get("extra")
    if isinstance(extra, dict) and "capacity_gb" in extra:
        rebuilt: dict[str, Any] = {}
        for k, v in extra.items():
            rebuilt["ram_gb" if k == "capacity_gb" else k] = v
        spec["extra"] = rebuilt
        changed = True

    # 已平鋪形狀（防禦：若某檔案曾被 normalize 過）
    if "capacity_gb" in spec:
        rebuilt: dict[str, Any] = {}
        for k, v in spec.items():
            rebuilt["ram_gb" if k == "capacity_gb" else k] = v
        item["spec"] = rebuilt
        changed = True

    return changed


def dump(doc: Any, compact: bool) -> str:
    if compact:
        return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def migrate_file(rel: str, compact: bool, check: bool) -> tuple[int, int]:
    path = REPO_ROOT / rel
    if not path.exists():
        return (0, 0)
    doc = json.loads(path.read_text(encoding="utf-8"))
    items = doc.get("items")
    changed = 0
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict) and migrate_item(it):
                changed += 1
    if changed and not check:
        path.write_text(dump(doc, compact), encoding="utf-8")
    return changed, len(items) if isinstance(items, list) else 0


def stats(items: list[Any]) -> dict[str, int]:
    mem = [it for it in items if isinstance(it, dict) and it.get("category") == "記憶體"]
    ssd = [it for it in items if isinstance(it, dict) and it.get("category") == "SSD"]
    hdd = [it for it in items if isinstance(it, dict) and it.get("category") == "HDD"]

    def has(it: dict, *keys: str) -> bool:
        spec = it.get("spec")
        if not isinstance(spec, dict):
            return False
        extra = spec.get("extra")
        for k in keys:
            if k in spec:
                return True
            if isinstance(extra, dict) and k in extra:
                return True
        return False

    return {
        "mem_ram_gb": sum(1 for it in mem if has(it, "ram_gb")),
        "mem_capacity_gb": sum(1 for it in mem if has(it, "capacity_gb")),
        "ssd_capacity_gb": sum(1 for it in ssd if has(it, "capacity_gb")),
        "hdd_capacity_gb": sum(1 for it in hdd if has(it, "capacity_gb")),
    }


def main(argv: list[str] | None = None) -> int:
    arg_parser = argparse.ArgumentParser(prog="migrate_ram_gb")
    arg_parser.add_argument("--check", action="store_true", help="僅驗證不寫檔")
    args = arg_parser.parse_args(argv)

    meta_before = json.loads((REPO_ROOT / "data" / "meta.json").read_text(encoding="utf-8"))

    total_changed = 0
    for rel, compact in TARGETS:
        changed, total = migrate_file(rel, compact, args.check)
        total_changed += changed
        path = REPO_ROOT / rel
        if path.exists():
            s = stats(json.loads(path.read_text(encoding="utf-8")).get("items", []))
            mode = "CHECK" if args.check else "OK"
            print(
                f"[{mode}] {rel}: changed={changed} total={total} "
                f"mem.ram_gb={s['mem_ram_gb']} mem.capacity_gb={s['mem_capacity_gb']} "
                f"ssd.capacity_gb={s['ssd_capacity_gb']} hdd.capacity_gb={s['hdd_capacity_gb']}"
            )

    meta_after = json.loads((REPO_ROOT / "data" / "meta.json").read_text(encoding="utf-8"))
    meta_unchanged = (meta_before == meta_after)
    print(f"meta.json unchanged={meta_unchanged} total={meta_after.get('total')} "
          f"counts.記憶體={meta_after.get('counts', {}).get('記憶體')} "
          f"counts.SSD={meta_after.get('counts', {}).get('SSD')} "
          f"counts.HDD={meta_after.get('counts', {}).get('HDD')}")
    print(f"total_items_changed={total_changed}")

    # 驗證不變量（寫檔後仍須成立）
    ok = True
    for rel, _ in TARGETS:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        s = stats(json.loads(path.read_text(encoding="utf-8")).get("items", []))
        if s["mem_capacity_gb"] != 0:
            print(f"FAIL: {rel} 記憶體仍有 capacity_gb（{s['mem_capacity_gb']} 筆）")
            ok = False
    if not meta_unchanged:
        print("FAIL: meta.json 被變更")
        ok = False
    if not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
