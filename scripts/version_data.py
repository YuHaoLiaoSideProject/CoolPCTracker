#!/usr/bin/env python3
"""data/ 異動判定 + api/ 衍生 API 建置（功能 002 §1.5 + AirTicketsPrice 模式）。

- 輸入：data/items.json（爬蟲 001 產出，{"meta":..., "items":[...]}）
  + data/meta.json（含 crawled_at / counts / total / status / changed）
- 比較基準：掃描 api/items/*.json 依 (日期 YYYYMMDD, 後綴) 升冪排序取最大者
  （上次最新快照；不存在 → 首次執行）
- 比較範圍：僅 items payload（crawled_at 不參與，避免時間戳造成永遠「有異動」）
- 有異動：date = crawled_at 轉 Asia/Taipei（UTC+8）日期 YYYYMMDD；掃 api/items/
  既有同日期檔決定下一檔名（無 → {date}.json；有 → {date}_1.json、{date}_2.json…），
  寫該檔（頂層含 crawled_at 與 items，separators=(",", ":")）→ 寫 api/latest.json
  （同內容，穩定端點）→ 重建 api/index.json（掃 api/items/*.json 得完整 files[] +
  併入 data/meta.json 的 merged meta + latest_file 指標）
- 無異動：不動任何檔案（工作目錄無變化 → 工作流跳過 commit）
- 輸出：stdout 印 changed=true|false 與 filename（異動時為新檔名，無異動為空）；
  若環境變數 GITHUB_OUTPUT 存在（GitHub Actions），以 key=value 追加寫入，供
  crawl.yml steps.version.outputs.changed / outputs.filename 使用

職責分層（AirTicketsPrice 模式）：data/ 是 crawler 唯一真相，api/ 是本模組
產出的對外 API 面（index.json 單一入口 + 日期制快照 + latest.json）。

對應 BDD：@business-rule @cache-busting（同日多份 → YYYYMMDD / YYYYMMDD_1 / …）、
@initial-setup（首次執行建立 api/items/{date}.json + meta.json）、
@regression（無異動 → changed=false、不寫檔）。
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SOURCE_URL = "https://www.coolpc.com.tw/m/m-list.php"
DESCRIPTION = "原價屋商品價格追蹤資料 API"

TAIPEI_TZ = timezone(timedelta(hours=8))  # Asia/Taipei（UTC+8，無日光節約）


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


def _taipei_date(crawled_at: str) -> str:
    """crawled_at（ISO 8601 UTC）→ Asia/Taipei（UTC+8）日期 YYYYMMDD。"""
    s = crawled_at.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TAIPEI_TZ).strftime("%Y%m%d")


def _file_key(name: str) -> tuple[int, int] | None:
    """解析日期制快照檔名 → (date_int, suffix)。suffix 0 = 無後綴。

    接受 YYYYMMDD.json / YYYYMMDD_N.json；不符合格式回傳 None（忽略該檔）。"""
    stem = name[:-5] if name.endswith(".json") else name
    if "_" in stem:
        date_part, suffix_part = stem.split("_", 1)
        if len(date_part) != 8 or not date_part.isdigit():
            return None
        if not suffix_part.isdigit():
            return None
        return (int(date_part), int(suffix_part))
    if len(stem) == 8 and stem.isdigit():
        return (int(stem), 0)
    return None


def _snapshot_paths(api_dir: Path) -> list[Path]:
    """掃 api/items/*.json 得日期制快照路徑（依 (date, suffix) 升冪排序）。"""
    items_dir = api_dir / "items"
    if not items_dir.is_dir():
        return []
    entries: list[tuple[tuple[int, int], Path]] = []
    for p in items_dir.glob("*.json"):
        key = _file_key(p.name)
        if key is not None:
            entries.append((key, p))
    entries.sort(key=lambda e: e[0])
    return [p for _, p in entries]


def _scan_files(api_dir: Path) -> list[dict]:
    """掃 api/items/*.json 得完整日期檔清單（依 (date, suffix) 升冪）。

    每檔含 file/crawled_at/total/url；「changed」僅由 build_index 依 meta.json
    補到最新檔（歷史檔省略）。"""
    files: list[dict] = []
    for p in _snapshot_paths(api_dir):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        files.append({
            "file": p.name,
            "crawled_at": payload.get("crawled_at"),
            "total": len(payload.get("items", [])),
            "url": f"api/items/{p.name}",
        })
    return files


def _next_filename(api_dir: Path, date_str: str) -> str:
    """依 api/items/ 既有同日期檔決定下一檔名：無 → {date}.json；有 → {date}_N.json。"""
    items_dir = api_dir / "items"
    suffixes: set[int] = set()
    if items_dir.is_dir():
        for p in items_dir.glob(f"{date_str}*.json"):
            key = _file_key(p.name)
            if key is not None and key[0] == int(date_str):
                suffixes.add(key[1])
    suffix = 0
    while suffix in suffixes:
        suffix += 1
    return f"{date_str}.json" if suffix == 0 else f"{date_str}_{suffix}.json"


def build_index(api_dir: Path, data_dir: Path) -> dict:
    """重建 api/index.json：完整 files[]（掃 api/items/）+ data/meta.json merged meta。

    merged meta：crawled_at/source/status/total/counts 併入 index 頂層；
    latest_file/latest 由掃描結果推導；changed 僅最新檔有（meta.json）。
    """
    meta = json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))
    files = _scan_files(api_dir)
    latest_file = files[-1]["url"] if files else None
    if files:
        changed = meta.get("changed")
        if changed is not None:
            files[-1]["changed"] = changed
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": meta.get("source", SOURCE_URL),
        "description": DESCRIPTION,
        "latest_file": latest_file,
        "latest": "api/latest.json",
        "crawled_at": meta.get("crawled_at"),
        "status": meta.get("status"),
        "total": meta.get("total"),
        "counts": meta.get("counts", {}),
        "files": files,
    }


def write_index(api_dir: Path, data_dir: Path) -> None:
    """寫 api/index.json（indent=2）。"""
    index = build_index(api_dir, data_dir)
    (api_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：python scripts/version_data.py [--data-dir data] [--api-dir api]（回傳 0）。

    流程：
    1. 讀 data/meta.json 與 data/items.json
    2. 掃 api/items/*.json 取最新快照（依 (date, suffix) 排序取最大）作為 diff baseline
    3. baseline 不存在（首次執行）→ 判定異動
    4. 否則 canonical JSON 僅比較 items payload：
       - 有異動 → date = crawled_at 轉台北日期；決定下一檔名；寫新快照 +
         api/latest.json + 重建 api/index.json
       - 無異動 → 不動任何檔案
    5. stdout 輸出 changed / filename，並依 GITHUB_OUTPUT 追加寫入。
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

    paths = _snapshot_paths(api_dir)
    changed = False
    if not paths:
        changed = True  # 首次執行：無比較基準 → 視為異動
    else:
        baseline = json.loads(paths[-1].read_text(encoding="utf-8"))
        changed = canonical(items["items"]) != canonical(baseline["items"])

    filename: str | None = None
    if changed:
        date_str = _taipei_date(meta["crawled_at"])
        filename = _next_filename(api_dir, date_str)
        items_dir.mkdir(parents=True, exist_ok=True)
        snapshot_payload = {"crawled_at": meta["crawled_at"], "items": items["items"]}
        snapshot_text = json.dumps(snapshot_payload, ensure_ascii=False,
                                   separators=(",", ":"))
        (items_dir / filename).write_text(snapshot_text, encoding="utf-8")
        # latest.json = 最新快照的穩定端點（同內容）
        (api_dir / "latest.json").write_text(snapshot_text, encoding="utf-8")
        # 重建 index（build_index 讀 meta.json 的 changed/total/counts/crawled_at
        # 併入 merged meta；files[] 由掃 api/items/ 推導）
        write_index(api_dir, data_dir)

    print(f"changed={'true' if changed else 'false'}")
    print(f"filename={filename or ''}")
    _write_github_output(changed, filename)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
