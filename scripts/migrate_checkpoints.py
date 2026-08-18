#!/usr/bin/env python3
"""008 遷移：舊全量 data/daily/ → seed checkpoint + 保留 legacy delta。

非破壞式：不刪任何既存 daily；等價可驗證：version_data 對「無 checkpoint」走
legacy 全量回放，與遷移前輸出一致（BDD Scenario 5 / 11 equivalence test）。
防線：meta.status == 'failed' 或 total == 0 → 不遷移（健康檢查延伸，防人工手術
壞資料污染）。冪等：data/checkpoints/ 已有 checkpoint → 已遷移，直接略過。

seed 錨點定案（loop-review 確認）：seed=最舊全量 daily 為歷史錨點，
保留所有舊 daily 為 legacy 全量回放源（不刪除不歸檔任何 daily）。
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class MigrateResult:
    seeded: bool                          # 是否新建 checkpoint
    checkpoint_file: Optional[str] = None # 建立的 checkpoint 檔名（YYYYMMDD.json）或 None
    kept_daily: list[str] = field(default_factory=list)  # 保留為 legacy 的 daily 檔名
    skipped: Optional[str] = None         # 防線/已遷移跳過原因


def migrate(data_dir: Path) -> MigrateResult:
    """執行遷移（純標準庫）：
    1. 讀 data/meta.json；防線：status=='failed' 或 total==0 → skipped，不遷移
    2. 冪等：data/checkpoints/ 已有 checkpoint → skipped，回傳現況
    3. 掃 data/daily/ 舊全量檔（只認 YYYYMMDD.json；壞檔跳過）
    4. seed：取最舊（檔名最小）全量 daily 內容 → 寫入 data/checkpoints/{最舊日}.json
    5. 保留所有舊 daily 為 legacy 全量回放源（**不刪除、不歸檔任何 daily**）
    6. 印出 summary
    """
    # 1. 防線：meta check
    meta_path = data_dir / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if not isinstance(meta, dict):
                meta = {}
        except (ValueError, OSError):
            meta = {}
        if meta.get("status") == "failed":
            return MigrateResult(seeded=False, skipped="status=failed")
        if meta.get("total") == 0:
            return MigrateResult(seeded=False, skipped="total=0")

    # 2. 冪等：已有 checkpoint → 已遷移
    cp_dir = data_dir / "checkpoints"
    if cp_dir.is_dir():
        existing = [p for p in cp_dir.glob("*.json")
                    if len(p.stem) == 8 and p.stem.isdigit()]
        if existing:
            return MigrateResult(seeded=False, skipped="already_migrated")

    # 3. 掃 daily 檔
    daily_dir = data_dir / "daily"
    if not daily_dir.is_dir():
        return MigrateResult(seeded=False, skipped="no_daily_dir")

    daily_files: list[tuple[str, Path]] = []
    for p in daily_dir.glob("*.json"):
        stem = p.stem
        if len(stem) == 8 and stem.isdigit():
            # 嘗試讀取，跳過壞檔
            try:
                payload = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    daily_files.append((stem, p))
            except (ValueError, OSError):
                continue

    if not daily_files:
        return MigrateResult(seeded=False, skipped="no_valid_daily_files")

    # 4. seed：取最舊全量 daily
    daily_files.sort(key=lambda x: x[0])  # 檔名升冪 = 日期升冪
    oldest_stem, oldest_path = daily_files[0]
    oldest_prices = json.loads(oldest_path.read_text(encoding="utf-8"))

    # 寫入 checkpoint
    cp_dir.mkdir(parents=True, exist_ok=True)
    cp_path = cp_dir / f"{oldest_stem}.json"
    cp_path.write_text(
        json.dumps(oldest_prices, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")

    # 5. 保留所有 daily（不刪除不歸檔）
    kept = [stem for stem, _ in daily_files]

    result = MigrateResult(
        seeded=True,
        checkpoint_file=f"{oldest_stem}.json",
        kept_daily=kept,
    )

    # 6. 印出 summary
    print(json.dumps({
        "seeded": result.seeded,
        "checkpoint_file": result.checkpoint_file,
        "kept_daily_count": len(result.kept_daily),
        "kept_daily_range": f"{result.kept_daily[0]}~{result.kept_daily[-1]}" if result.kept_daily else "",
        "skipped": result.skipped,
    }, ensure_ascii=False, indent=2))

    return result


def main(argv: list[str] | None = None) -> int:
    """CLI：python scripts/migrate_checkpoints.py [--data-dir data]"""
    arg_parser = argparse.ArgumentParser(prog="migrate_checkpoints")
    arg_parser.add_argument("--data-dir", default="data", type=Path)
    args = arg_parser.parse_args(argv)

    result = migrate(args.data_dir)

    if result.skipped:
        print(f"Skipped: {result.skipped}", file=sys.stderr)
        return 0
    if result.seeded:
        print(f"Migration complete: seeded checkpoint {result.checkpoint_file}, "
              f"kept {len(result.kept_daily)} daily files as legacy", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
