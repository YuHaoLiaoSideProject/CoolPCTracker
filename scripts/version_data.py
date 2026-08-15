#!/usr/bin/env python3
"""data/ 異動判定與 cache-busting 版本化（功能 002 §1.5）。

- 輸入：data/items.json（爬蟲 001 產出，{"meta":..., "items":[...]}）
  + data/meta.json（含 version / crawled_at / counts / total / status）
- 比較基準：data/items.v{prev}.json（上次版本化快照；不存在 → 首次執行）
- 比較範圍：僅 items payload（crawled_at 不參與，避免時間戳造成永遠「有異動」）
- 有異動：next = prev + 1，寫 items.v{next}.json（頂層含 crawled_at 與 items，
  separators=(",", ":")）+ 更新 meta.json version（indent=2）
- 無異動：不動任何檔案（工作目錄無變化 → 工作流跳過 commit）
- 輸出：stdout 印 changed=true|false 與 version=N；若環境變數 GITHUB_OUTPUT
  存在（GitHub Actions），以 key=value 追加寫入，供 crawl.yml
  steps.version.outputs.changed / outputs.version 使用

對應 BDD：@business-rule @cache-busting（1→2 / 5→6 / 9→10）、
@initial-setup（首次執行建立 items.v1.json + meta.json）、
@regression（無異動 → changed=false、不寫檔）。
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def canonical(obj: Any) -> str:
    """canonical JSON：dict key 排序 + 不跳脫非 ASCII（僅供比較，無關寫檔格式）。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def _write_github_output(changed: bool, version: int) -> None:
    """若 GITHUB_OUTPUT 存在（GitHub Actions），以 key=value 追加寫入兩行。

    與工作流 `id: version` step 的 `steps.version.outputs.changed` /
    `outputs.version` 對應；檔案不存在時由 open("a") 建立。"""
    out_path = os.environ.get("GITHUB_OUTPUT")
    if not out_path:
        return
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(f"changed={'true' if changed else 'false'}\n")
        f.write(f"version={version}\n")


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：python scripts/version_data.py [--data-dir data]（回傳 0）。

    流程（§1.5）：
    1. 讀 meta.json 取 prev version（欄位不存在視為 0）
    2. items.v{prev}.json 不存在（首次執行）→ 判定異動，next = 1
    3. 否則 canonical JSON 僅比較 items payload：
       - 有異動 → next = prev + 1，寫 items.v{next}.json + 更新 meta.json version
       - 無異動 → 不動任何檔案
    4. stdout 輸出 changed / version，並依 GITHUB_OUTPUT 追加寫入。
    """
    arg_parser = argparse.ArgumentParser(prog="version_data")
    arg_parser.add_argument("--data-dir", default="data", type=Path)
    args = arg_parser.parse_args(argv)
    data_dir: Path = args.data_dir

    meta = json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))
    items = json.loads((data_dir / "items.json").read_text(encoding="utf-8"))

    prev = int(meta.get("version", 0))
    prev_file = data_dir / f"items.v{prev}.json"

    changed = False
    if not prev_file.exists():
        changed = True  # 首次執行：無比較基準 → 視為異動，next = 1
    else:
        prev_payload = json.loads(prev_file.read_text(encoding="utf-8"))
        changed = canonical(items["items"]) != canonical(prev_payload["items"])

    version = prev
    if changed:
        version = prev + 1
        (data_dir / f"items.v{version}.json").write_text(
            json.dumps({"crawled_at": meta["crawled_at"], "items": items["items"]},
                       ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
        meta["version"] = version
        (data_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"changed={'true' if changed else 'false'}")
    print(f"version={version}")
    _write_github_output(changed, version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
