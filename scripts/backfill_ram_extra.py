#!/usr/bin/env python3
"""一次性資料回填：為 6 筆 Biwin/Origin code 記憶體補上 spec.extra（可重跑、冪等）。

背景（004 資料缺口）：
- crawler/spec_parser.py 的 _RAM_BRANDS 缺「Biwin/佰維」「Origin code」中英別名，
  導致 6 筆記憶體品牌剝離失敗 → spec.extra 為空、brand/model=None、ram_gb 缺失。
- 修正 parser 後，本腳本以「離線重新解析」回填既有資料，不跑 live 爬蟲。

回填規則（僅 category == "記憶體"，且重新解析後與既有 spec 不同才寫入）：
- 以 parse_spec(category, name) 離線重新解析，asdict 寫回 item["spec"]。
- 其餘分類（CPU/顯示卡/主機板/SSD/HDD/記憶卡/套裝/劈發價）一律不動。
- meta.json 不變（total/counts 皆為原始爬蟲統計，與 spec 內容無關）。

處理檔案（與前端 dev/build 讀取路徑一致）：
- data/items.json（indent=2 + 尾換行，crawler 產出格式）
- data/items.v2.json、web/public/data/items.v2.json、web/dist/data/items.v2.json
  （compact separators；web/dist/data/ 為 build 產物、gitignored，此處直接同步）

用法：
    python scripts/backfill_ram_extra.py [--check]
  --check：僅驗證（dry-run）不寫檔。
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

# 直接以 `python scripts/backfill_ram_extra.py` 執行時，repo 根目錄不在 sys.path；
# 加入 bootstrap 讓 `import crawler` 可用（pytest 路徑由 conftest 提供，不影響）。
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from crawler.spec_parser import parse_spec

REPO_ROOT = _REPO_ROOT

# (路徑, compact 與否)；compact=True 用 separators=(",", ":") 無尾換行，
# 否則 indent=2 且尾端換行（與 crawler 產出 items.json 一致）。
TARGETS: list[tuple[str, bool]] = [
    ("data/items.json", False),
    ("data/items.v2.json", True),
    ("web/public/data/items.v2.json", True),
    ("web/dist/data/items.v2.json", True),  # build 產物，gitignored，僅同步不提交
]


def backfill_item(item: dict[str, Any]) -> bool:
    """就地回填單一 item；回傳是否變更。僅處理 category == 記憶體。"""
    if item.get("category") != "記憶體":
        return False
    name = item.get("name")
    if not isinstance(name, str) or not name:
        return False
    new_spec = asdict(parse_spec("記憶體", name))
    if item.get("spec") == new_spec:
        return False
    item["spec"] = new_spec
    return True


def dump(doc: Any, compact: bool) -> str:
    if compact:
        return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def backfill_file(rel: str, compact: bool, check: bool) -> tuple[int, int]:
    path = REPO_ROOT / rel
    if not path.exists():
        return (0, 0)
    doc = json.loads(path.read_text(encoding="utf-8"))
    items = doc.get("items")
    changed = 0
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict) and backfill_item(it):
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

    mem_empty = sum(
        1
        for it in mem
        if isinstance(it.get("spec"), dict) and not it["spec"].get("extra")
    )
    return {
        "mem_ram_gb": sum(1 for it in mem if has(it, "ram_gb")),
        "mem_empty_extra": mem_empty,
        "ssd_capacity_gb": sum(1 for it in ssd if has(it, "capacity_gb")),
        "hdd_capacity_gb": sum(1 for it in hdd if has(it, "capacity_gb")),
    }


def main(argv: list[str] | None = None) -> int:
    arg_parser = argparse.ArgumentParser(prog="backfill_ram_extra")
    arg_parser.add_argument("--check", action="store_true", help="僅驗證不寫檔")
    args = arg_parser.parse_args(argv)

    meta_before = json.loads((REPO_ROOT / "data" / "meta.json").read_text(encoding="utf-8"))

    total_changed = 0
    for rel, compact in TARGETS:
        changed, total = backfill_file(rel, compact, args.check)
        total_changed += changed
        path = REPO_ROOT / rel
        if path.exists():
            s = stats(json.loads(path.read_text(encoding="utf-8")).get("items", []))
            mode = "CHECK" if args.check else "OK"
            print(
                f"[{mode}] {rel}: changed={changed} total={total} "
                f"mem.ram_gb={s['mem_ram_gb']} mem.empty_extra={s['mem_empty_extra']} "
                f"ssd.capacity_gb={s['ssd_capacity_gb']} hdd.capacity_gb={s['hdd_capacity_gb']}"
            )

    meta_after = json.loads((REPO_ROOT / "data" / "meta.json").read_text(encoding="utf-8"))
    meta_unchanged = (meta_before == meta_after)
    print(f"meta.json unchanged={meta_unchanged} total={meta_after.get('total')} "
          f"counts.記憶體={meta_after.get('counts', {}).get('記憶體')} "
          f"counts.SSD={meta_after.get('counts', {}).get('SSD')} "
          f"counts.HDD={meta_after.get('counts', {}).get('HDD')}")
    print(f"total_items_changed={total_changed}")

    # 驗證不變量（僅寫檔後強制；--check 為 dry-run，未寫入故不強制）
    ok = True
    if not args.check:
        for rel, _ in TARGETS:
            path = REPO_ROOT / rel
            if not path.exists():
                continue
            s = stats(json.loads(path.read_text(encoding="utf-8")).get("items", []))
            if s["mem_empty_extra"] != 0:
                print(f"FAIL: {rel} 記憶體仍有空 spec.extra（{s['mem_empty_extra']} 筆）")
                ok = False
        if not meta_unchanged:
            print("FAIL: meta.json 被變更")
            ok = False
    if not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
