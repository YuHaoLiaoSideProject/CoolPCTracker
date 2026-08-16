#!/usr/bin/env python3
"""data/ 異動判定 + api/ 衍生 API 建置（功能 002 §1.5 + AirTicketsPrice 模式）。

- 輸入：data/items.json（爬蟲 001 產出，{"meta":..., "items":[...]}）
  + data/meta.json（含 version / crawled_at / counts / total / status / changed）
- 比較基準：api/items/v{prev}.json（上次版本化快照；不存在 → 首次執行）
- 比較範圍：僅 items payload（crawled_at 不參與，避免時間戳造成永遠「有異動」）
- 有異動：next = prev + 1，寫 api/items/v{next}.json（頂層含 crawled_at 與 items，
  separators=(",", ":")）→ 寫 api/latest.json（同內容，穩定端點）→ 重建
  api/index.json（掃 api/items/v*.json 得完整 versions[] + 併入 data/meta.json 的
  merged meta + bump latest_version）→ 更新 data/meta.json 的 version（indent=2）
- 無異動：不動任何檔案（工作目錄無變化 → 工作流跳過 commit）
- 輸出：stdout 印 changed=true|false 與 version=N；若環境變數 GITHUB_OUTPUT
  存在（GitHub Actions），以 key=value 追加寫入，供 crawl.yml
  steps.version.outputs.changed / outputs.version 使用

職責分層（AirTicketsPrice 模式）：data/ 是 crawler 唯一真相，api/ 是本模組
產出的對外 API 面（index.json 單一入口 + 版本化快照 + latest.json）。

對應 BDD：@business-rule @cache-busting（1→2 / 5→6 / 9→10）、
@initial-setup（首次執行建立 api/items/v1.json + meta.json）、
@regression（無異動 → changed=false、不寫檔）。
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOURCE_URL = "https://www.coolpc.com.tw/m/m-list.php"
DESCRIPTION = "原價屋商品價格追蹤資料 API"


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


def _version_from_name(name: str) -> int:
    """從快照檔名（如 v3.json / v10.json）解析整數版本號。"""
    stem = name[:-5] if name.endswith(".json") else name
    return int(stem[1:])


def _scan_versions(api_dir: Path) -> list[dict]:
    """掃 api/items/v*.json 得完整版本歷史（依版本號升冪）。

    每版含 version/crawled_at/total/url；「changed」僅由 build_index 依 meta.json
    補到最新版（歷史版省略）。"""
    items_dir = api_dir / "items"
    versions: list[dict] = []
    if not items_dir.is_dir():
        return versions
    paths = sorted(items_dir.glob("v*.json"), key=lambda p: _version_from_name(p.name))
    for p in paths:
        try:
            n = _version_from_name(p.name)
        except (ValueError, IndexError):
            continue
        payload = json.loads(p.read_text(encoding="utf-8"))
        versions.append({
            "version": n,
            "crawled_at": payload.get("crawled_at"),
            "total": len(payload.get("items", [])),
            "url": f"api/items/v{n}.json",
        })
    return versions


def build_index(api_dir: Path, data_dir: Path) -> dict:
    """重建 api/index.json：完整 versions[]（掃 api/items/）+ data/meta.json merged meta。

    merged meta：crawled_at/source/status/total/counts 併入 index 頂層；
    latest_version/latest/latest_items 由掃描結果推導；changed 僅最新版有（meta.json）。
    """
    meta = json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))
    versions = _scan_versions(api_dir)
    latest_version = versions[-1]["version"] if versions else 0
    if versions:
        changed = meta.get("changed")
        if changed is not None:
            versions[-1]["changed"] = changed
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": meta.get("source", SOURCE_URL),
        "description": DESCRIPTION,
        "latest_version": latest_version,
        "latest": "api/latest.json",
        "latest_items": f"api/items/v{latest_version}.json" if latest_version else None,
        "crawled_at": meta.get("crawled_at"),
        "status": meta.get("status"),
        "total": meta.get("total"),
        "counts": meta.get("counts", {}),
        "versions": versions,
    }


def write_index(api_dir: Path, data_dir: Path) -> None:
    """寫 api/index.json（indent=2）。"""
    index = build_index(api_dir, data_dir)
    (api_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：python scripts/version_data.py [--data-dir data] [--api-dir api]（回傳 0）。

    流程：
    1. 讀 data/meta.json 取 prev version（計數器不動，欄位不存在視為 0）
    2. api/items/v{prev}.json 不存在（首次執行）→ 判定異動，next = 1
    3. 否則 canonical JSON 僅比較 items payload：
       - 有異動 → next = prev + 1，寫 api/items/v{next}.json + api/latest.json
         + 重建 api/index.json + 更新 data/meta.json version
       - 無異動 → 不動任何檔案
    4. stdout 輸出 changed / version，並依 GITHUB_OUTPUT 追加寫入。
    """
    arg_parser = argparse.ArgumentParser(prog="version_data")
    arg_parser.add_argument("--data-dir", default="data", type=Path)
    arg_parser.add_argument("--api-dir", default="api", type=Path)
    args = arg_parser.parse_args(argv)
    data_dir: Path = args.data_dir
    api_dir: Path = args.api_dir
    items_dir: Path = api_dir / "items"

    meta = json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))
    items = json.loads((data_dir / "items.json").read_text(encoding="utf-8"))

    prev = int(meta.get("version", 0))
    prev_file = items_dir / f"v{prev}.json"

    changed = False
    if not prev_file.exists():
        changed = True  # 首次執行：無比較基準 → 視為異動，next = 1
    else:
        prev_payload = json.loads(prev_file.read_text(encoding="utf-8"))
        changed = canonical(items["items"]) != canonical(prev_payload["items"])

    version = prev
    if changed:
        version = prev + 1
        items_dir.mkdir(parents=True, exist_ok=True)
        snapshot_payload = {"crawled_at": meta["crawled_at"], "items": items["items"]}
        snapshot_text = json.dumps(snapshot_payload, ensure_ascii=False,
                                   separators=(",", ":"))
        (items_dir / f"v{version}.json").write_text(snapshot_text, encoding="utf-8")
        # latest.json = 最新快照的穩定端點（同內容）
        (api_dir / "latest.json").write_text(snapshot_text, encoding="utf-8")
        # 先 bump meta.json version，再重建 index（build_index 讀 meta.json 的
        # changed/total/counts/crawled_at 併入 merged meta）
        meta["version"] = version
        (data_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        write_index(api_dir, data_dir)

    print(f"changed={'true' if changed else 'false'}")
    print(f"version={version}")
    _write_github_output(changed, version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
