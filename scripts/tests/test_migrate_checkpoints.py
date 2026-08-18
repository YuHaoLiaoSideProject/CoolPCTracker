"""migrate_checkpoints.py 單元測試（008 遷移腳本）。

涵蓋：seed=最舊全量 daily、保留所有舊 daily（不刪除不歸檔）、
防線（failed/total=0 不遷移）、冪等（已遷移略過）、非破壞（不刪任何 daily）。
測試一律使用 pytest tmp_path。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.migrate_checkpoints import MigrateResult, migrate


def write_daily(data_dir: Path, filename: str, prices: dict) -> None:
    """寫 data/daily/{filename}.json。"""
    daily_dir = data_dir / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    (daily_dir / f"{filename}.json").write_text(
        json.dumps(prices, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")


def write_meta(data_dir: Path, meta: dict) -> None:
    """寫 data/meta.json。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8")


# ── seed + 保留 ────────────────────────────────────────────────────────────

class TestSeedAndKeep:
    def test_seed_oldest_daily_as_checkpoint(self, tmp_path):
        """seed=最舊全量 daily 為 checkpoint。"""
        write_daily(tmp_path, "20260801", {"a": 100, "b": 200})
        write_daily(tmp_path, "20260810", {"a": 110, "b": 200})
        write_daily(tmp_path, "20260817", {"a": 110, "b": 210})
        write_meta(tmp_path, {"status": "ok", "total": 2})

        result = migrate(tmp_path)

        assert result.seeded is True
        assert result.checkpoint_file == "20260801.json"
        # checkpoint 內容 = 最舊 daily
        cp = json.loads((tmp_path / "checkpoints" / "20260801.json").read_text())
        assert cp == {"a": 100, "b": 200}

    def test_keeps_all_daily_files(self, tmp_path):
        """保留所有舊 daily 為 legacy 全量回放源（不刪除不歸檔）。"""
        write_daily(tmp_path, "20260801", {"a": 100})
        write_daily(tmp_path, "20260810", {"a": 110})
        write_daily(tmp_path, "20260817", {"a": 110})
        write_meta(tmp_path, {"status": "ok", "total": 1})

        result = migrate(tmp_path)

        assert len(result.kept_daily) == 3
        assert set(result.kept_daily) == {"20260801", "20260810", "20260817"}
        # 所有 daily 檔仍存在
        assert (tmp_path / "daily" / "20260801.json").exists()
        assert (tmp_path / "daily" / "20260810.json").exists()
        assert (tmp_path / "daily" / "20260817.json").exists()
        # 無 archive 目錄
        assert not (tmp_path / "daily_legacy_archive").exists()

    def test_skips_corrupted_daily(self, tmp_path):
        """壞檔（非 JSON object）跳過不參與 seed 選擇。"""
        write_daily(tmp_path, "20260801", {"a": 100})
        # 壞檔
        (tmp_path / "daily" / "20260805.json").write_text("not json!!!")
        write_daily(tmp_path, "20260810", {"a": 110})
        write_meta(tmp_path, {"status": "ok", "total": 1})

        result = migrate(tmp_path)

        # seed = 最舊有效 daily（20260801），不是壞檔
        assert result.seeded is True
        assert result.checkpoint_file == "20260801.json"
        assert len(result.kept_daily) == 2  # 20260805 被跳過

    def test_skips_non_object_daily(self, tmp_path):
        """非 object daily（如 array）跳過。"""
        write_daily(tmp_path, "20260801", {"a": 100})
        (tmp_path / "daily" / "20260805.json").write_text('[1, 2, 3]')
        write_meta(tmp_path, {"status": "ok", "total": 1})

        result = migrate(tmp_path)
        assert result.checkpoint_file == "20260801.json"
        assert len(result.kept_daily) == 1


# ── 防線 ────────────────────────────────────────────────────────────────────

class TestGuardLines:
    def test_failed_status_skips(self, tmp_path):
        """meta.status == 'failed' → 不遷移。"""
        write_daily(tmp_path, "20260801", {"a": 100})
        write_meta(tmp_path, {"status": "failed", "total": 1})

        result = migrate(tmp_path)
        assert result.seeded is False
        assert result.skipped == "status=failed"
        assert not (tmp_path / "checkpoints").exists()

    def test_total_zero_skips(self, tmp_path):
        """meta.total == 0 → 不遷移。"""
        write_daily(tmp_path, "20260801", {"a": 100})
        write_meta(tmp_path, {"status": "ok", "total": 0})

        result = migrate(tmp_path)
        assert result.seeded is False
        assert result.skipped == "total=0"


# ── 冪等 ────────────────────────────────────────────────────────────────────

class TestIdempotent:
    def test_already_migrated_skips(self, tmp_path):
        """data/checkpoints/ 已有 checkpoint → 已遷移，略過。"""
        write_daily(tmp_path, "20260801", {"a": 100})
        write_meta(tmp_path, {"status": "ok", "total": 1})
        # 預先建立一個 checkpoint
        (tmp_path / "checkpoints").mkdir(parents=True)
        (tmp_path / "checkpoints" / "20260801.json").write_text('{"a": 999}')

        result = migrate(tmp_path)
        assert result.seeded is False
        assert result.skipped == "already_migrated"
        # 原有 checkpoint 不被覆蓋
        cp = json.loads((tmp_path / "checkpoints" / "20260801.json").read_text())
        assert cp == {"a": 999}


# ── 無 daily ────────────────────────────────────────────────────────────────

class TestNoDaily:
    def test_no_daily_dir(self, tmp_path):
        """無 data/daily/ 目錄 → skipped。"""
        write_meta(tmp_path, {"status": "ok", "total": 1})
        result = migrate(tmp_path)
        assert result.seeded is False
        assert result.skipped == "no_daily_dir"

    def test_empty_daily_dir(self, tmp_path):
        """data/daily/ 為空 → skipped。"""
        (tmp_path / "daily").mkdir(parents=True)
        write_meta(tmp_path, {"status": "ok", "total": 1})
        result = migrate(tmp_path)
        assert result.seeded is False
        assert result.skipped == "no_valid_daily_files"
