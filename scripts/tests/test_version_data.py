"""version_data.py 單元測試（功能 002 §1.5 + BDD @business-rule @cache-busting、
@initial-setup、@regression）。

涵蓋：首次執行（無 items.v0.json → next=1）、異動遞增（Example 表 1→2/5→6/9→10）、
無異動不寫檔、crawled_at 差異不視為異動、--data-dir 自訂目錄、GITHUB_OUTPUT 寫入。
測試一律使用 pytest tmp_path（可 chdir），不碰真實檔案系統。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import version_data

CRAWLED_OLD = "2026-08-15T06:00:00+00:00"
CRAWLED_NEW = "2026-08-16T06:00:00+00:00"

# 價格相同、內容相同但 dict key 順序不同 → 驗證 canonical（sort_keys）比較
ITEM_A = {"id": "cpu-1", "category": "CPU", "name": "Intel i5-13600K", "price": 9990}
ITEM_A_SHUFFLED = {"price": 9990, "name": "Intel i5-13600K", "category": "CPU", "id": "cpu-1"}
ITEM_B = {"id": "cpu-1", "category": "CPU", "name": "Intel i5-13600K", "price": 9500}


def write_data(data_dir: Path, *, version: int | None, crawled_at: str,
               items: list[dict]) -> None:
    """寫出爬蟲 001 產物：items.json（{"meta":..., "items":[...]}）+ meta.json。
    version=None 表示 meta 中無 version 欄位（「不存在視為 0」路徑）。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    meta: dict = {"crawled_at": crawled_at, "source": "https://www.coolpc.com.tw/m/m-list.php",
                  "total": len(items)}
    if version is not None:
        meta["version"] = version
    (data_dir / "items.json").write_text(
        json.dumps({"meta": meta, "items": items}, ensure_ascii=False), encoding="utf-8")
    (data_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def write_version_snapshot(data_dir: Path, version: int, crawled_at: str,
                           items: list[dict]) -> Path:
    """寫出上次版本化快照 items.v{version}.json（頂層含 crawled_at 與 items）。"""
    path = data_dir / f"items.v{version}.json"
    path.write_text(json.dumps({"crawled_at": crawled_at, "items": items},
                               ensure_ascii=False), encoding="utf-8")
    return path


def snapshot(data_dir: Path) -> dict[str, bytes]:
    """記錄 data 目錄全部檔案內容（path → bytes），供「不寫任何檔案」比對。"""
    return {p.name: p.read_bytes() for p in sorted(data_dir.iterdir())}


def run_stdout(capsys, data_dir: Path) -> tuple[str, str]:
    """執行 main([--data-dir]) 並回傳 (changed 行, version 行)。"""
    code = version_data.main(["--data-dir", str(data_dir)])
    out = capsys.readouterr().out
    lines = out.strip().splitlines()
    assert code == 0
    assert len(lines) == 2
    return lines[0], lines[1]


# ── 首次執行（BDD @edge-case @initial-setup）───────────────────────────────

class TestFirstRun:
    def test_no_prev_snapshot_creates_v1(self, tmp_path, capsys):
        """無 items.v0.json（meta 亦無 version 欄位）→ changed=true、version=1、
        items.v1.json 含 crawled_at 與 items、meta.json version=1。"""
        write_data(tmp_path, version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        changed_line, version_line = run_stdout(capsys, tmp_path)

        assert changed_line == "changed=true"
        assert version_line == "version=1"

        snapshot_file = tmp_path / "items.v1.json"
        assert snapshot_file.exists()
        payload = json.loads(snapshot_file.read_text(encoding="utf-8"))
        assert payload["crawled_at"] == CRAWLED_NEW
        assert payload["items"] == [ITEM_A]

        meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
        assert meta["version"] == 1

    def test_first_run_snapshot_uses_compact_separators(self, tmp_path, capsys):
        """items.v{n}.json 寫入格式：separators=(",", ":")（無多餘空白）。"""
        write_data(tmp_path, version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])
        run_stdout(capsys, tmp_path)

        text = (tmp_path / "items.v1.json").read_text(encoding="utf-8")
        assert '"crawled_at":"' in text          # 冒號後無空白
        assert '", "items":[' not in text        # 逗號後無空白
        assert text.startswith('{"crawled_at"')

    def test_meta_written_with_indent(self, tmp_path, capsys):
        """meta.json 寫入格式：indent=2。"""
        write_data(tmp_path, version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])
        run_stdout(capsys, tmp_path)

        text = (tmp_path / "meta.json").read_text(encoding="utf-8")
        assert '\n  "version": 1' in text
        assert '\n  "crawled_at": "' in text


# ── 異動遞增（BDD @business-rule @cache-busting，Example 全覆蓋）────────────

class TestIncrement:
    @pytest.mark.parametrize("prev", [1, 5, 9])
    def test_changed_increments_version(self, tmp_path, capsys, prev):
        """prev 1→2 / 5→6 / 9→10：next=prev+1、寫 items.v{next}.json
        （含本次 crawled_at 與新 items）、meta.json version 同步、舊快照不動。"""
        next_v = prev + 1
        write_version_snapshot(tmp_path, prev, CRAWLED_OLD, [ITEM_A])
        write_data(tmp_path, version=prev, crawled_at=CRAWLED_NEW, items=[ITEM_B])

        changed_line, version_line = run_stdout(capsys, tmp_path)

        assert changed_line == "changed=true"
        assert version_line == f"version={next_v}"

        payload = json.loads((tmp_path / f"items.v{next_v}.json").read_text(encoding="utf-8"))
        assert payload["crawled_at"] == CRAWLED_NEW
        assert payload["items"] == [ITEM_B]

        meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
        assert meta["version"] == next_v

        # 舊快照不被覆寫
        assert json.loads((tmp_path / f"items.v{prev}.json").read_text(encoding="utf-8"))["items"] == [ITEM_A]


# ── 無異動（BDD @business-rule @regression）────────────────────────────────

class TestNoChange:
    def test_no_change_writes_nothing(self, tmp_path, capsys):
        """items 完全一致（含 dict key 順序不同，驗證 canonical sort_keys）→
        changed=false、version 不變、目錄內無任何檔案新增或變更。"""
        write_version_snapshot(tmp_path, 5, CRAWLED_OLD, [ITEM_A])
        write_data(tmp_path, version=5, crawled_at=CRAWLED_NEW, items=[ITEM_A_SHUFFLED])
        before = snapshot(tmp_path)

        changed_line, version_line = run_stdout(capsys, tmp_path)

        assert changed_line == "changed=false"
        assert version_line == "version=5"
        assert snapshot(tmp_path) == before          # 一個 byte 都沒變
        assert not (tmp_path / "items.v6.json").exists()

    def test_no_change_when_only_crawled_at_differs(self, tmp_path, capsys):
        """crawled_at 不同但 items 相同 → 判為無異動（時間戳不參與比對）。"""
        write_version_snapshot(tmp_path, 3, CRAWLED_OLD, [ITEM_A])
        write_data(tmp_path, version=3, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        changed_line, version_line = run_stdout(capsys, tmp_path)

        assert changed_line == "changed=false"
        assert version_line == "version=3"
        assert not (tmp_path / "items.v4.json").exists()


# ── 目錄參數與 GITHUB_OUTPUT ────────────────────────────────────────────────

class TestCliAndOutput:
    def test_custom_data_dir_nested_path(self, tmp_path, capsys):
        """--data-dir 支援任意自訂路徑（巢狀目錄）。"""
        custom = tmp_path / "custom" / "nested"
        write_data(custom, version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        code = version_data.main(["--data-dir", str(custom)])

        assert code == 0
        assert (custom / "items.v1.json").exists()
        assert json.loads((custom / "meta.json").read_text(encoding="utf-8"))["version"] == 1
        assert "changed=true" in capsys.readouterr().out

    def test_default_data_dir_relative(self, tmp_path, monkeypatch, capsys):
        """未指定 --data-dir 時使用預設相對路徑 "data"（與 crawler.main 一致）。"""
        monkeypatch.chdir(tmp_path)
        write_data(tmp_path / "data", version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        code = version_data.main([])

        assert code == 0
        assert (tmp_path / "data" / "items.v1.json").exists()
        assert "version=1" in capsys.readouterr().out

    def test_github_output_written_on_change(self, tmp_path, monkeypatch, capsys):
        """GITHUB_OUTPUT 存在時以 key=value 追加寫入 changed/version 兩行（首次執行）。"""
        out_path = tmp_path / "github_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_path))
        write_data(tmp_path, version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        assert version_data.main(["--data-dir", str(tmp_path)]) == 0

        assert out_path.read_text(encoding="utf-8").splitlines() == ["changed=true", "version=1"]

    def test_github_output_written_on_no_change(self, tmp_path, monkeypatch, capsys):
        """GITHUB_OUTPUT 在無異動時寫 changed=false 與原版本號。"""
        out_path = tmp_path / "github_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_path))
        write_version_snapshot(tmp_path, 5, CRAWLED_OLD, [ITEM_A])
        write_data(tmp_path, version=5, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        assert version_data.main(["--data-dir", str(tmp_path)]) == 0

        assert out_path.read_text(encoding="utf-8").splitlines() == ["changed=false", "version=5"]

    def test_github_output_appends_to_existing_file(self, tmp_path, monkeypatch, capsys):
        """GITHUB_OUTPUT 為追加寫入（不覆蓋既有內容）。"""
        out_path = tmp_path / "github_output.txt"
        out_path.write_text("other=1\n", encoding="utf-8")
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_path))
        write_data(tmp_path, version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        assert version_data.main(["--data-dir", str(tmp_path)]) == 0

        assert out_path.read_text(encoding="utf-8").splitlines() == ["other=1", "changed=true", "version=1"]

    def test_github_output_absent_writes_nothing(self, tmp_path, monkeypatch, capsys):
        """無 GITHUB_OUTPUT 環境變數 → 僅 stdout 輸出，不額外寫檔。"""
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
        write_data(tmp_path, version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        assert version_data.main(["--data-dir", str(tmp_path)]) == 0

        files = {p.name for p in tmp_path.iterdir()}
        assert "github_output.txt" not in files
        assert "changed=true" in capsys.readouterr().out
