"""version_data.py 單元測試（功能 002 §1.5 + BDD @business-rule @cache-busting、
@initial-setup、@regression）＋ AirTicketsPrice 模式（api/ 衍生 API 成品）。

涵蓋：首次執行（無 api/items/v*.json → next=1）、異動遞增（Example 表 1→2/5→6/9→10）、
index.json 完整 versions[] + merged meta + changed 僅最新版、latest.json 穩定端點、
無異動不寫檔、crawled_at 差異不視為異動、--data-dir/--api-dir 自訂目錄、
GITHUB_OUTPUT 寫入。
測試一律使用 pytest tmp_path（可 chdir），不碰真實檔案系統。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import version_data

CRAWLED_OLD = "2026-08-15T06:00:00+00:00"
CRAWLED_NEW = "2026-08-16T06:00:00+00:00"
SOURCE = "https://www.coolpc.com.tw/m/m-list.php"

# 價格相同、內容相同但 dict key 順序不同 → 驗證 canonical（sort_keys）比較
ITEM_A = {"id": "cpu-1", "category": "CPU", "name": "Intel i5-13600K", "price": 9990}
ITEM_A_SHUFFLED = {"price": 9990, "name": "Intel i5-13600K", "category": "CPU", "id": "cpu-1"}
ITEM_B = {"id": "cpu-1", "category": "CPU", "name": "Intel i5-13600K", "price": 9500}
ITEM_C = {"id": "cpu-1", "category": "CPU", "name": "Intel i5-13600K", "price": 9100}


def write_data(data_dir: Path, *, version: int | None, crawled_at: str,
               items: list[dict], total: int | None = None,
               counts: dict | None = None, status: str = "ok",
               changed: int | None = None) -> None:
    """寫出爬蟲 001 產物：items.json（{"meta":..., "items":[...]}）+ meta.json。
    version=None 表示 meta 中無 version 欄位（「不存在視為 0」路徑）。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    meta: dict = {"crawled_at": crawled_at, "source": SOURCE,
                  "total": total if total is not None else len(items),
                  "counts": counts if counts is not None else {},
                  "status": status}
    if version is not None:
        meta["version"] = version
    if changed is not None:
        meta["changed"] = changed
    (data_dir / "items.json").write_text(
        json.dumps({"meta": meta, "items": items}, ensure_ascii=False), encoding="utf-8")
    (data_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def write_snapshot(api_dir: Path, version: int, crawled_at: str,
                   items: list[dict]) -> Path:
    """寫出上次版本化快照 api/items/v{version}.json（頂層含 crawled_at 與 items）。"""
    items_dir = api_dir / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    path = items_dir / f"v{version}.json"
    path.write_text(json.dumps({"crawled_at": crawled_at, "items": items},
                               ensure_ascii=False), encoding="utf-8")
    return path


def snapshot_all(data_dir: Path, api_dir: Path) -> dict[str, bytes]:
    """記錄 data 與 api 目錄全部檔案內容（相對路徑 → bytes），供「不寫任何檔案」比對。"""
    result: dict[str, bytes] = {}
    for base in (data_dir, api_dir):
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file():
                result[f"{base.name}/{p.relative_to(base)}"] = p.read_bytes()
    return result


def run_main(capsys, data_dir: Path, api_dir: Path) -> tuple[str, str]:
    """執行 main([--data-dir, --api-dir]) 並回傳 (changed 行, version 行)。"""
    code = version_data.main(["--data-dir", str(data_dir), "--api-dir", str(api_dir)])
    out = capsys.readouterr().out
    lines = out.strip().splitlines()
    assert code == 0
    assert len(lines) == 2
    return lines[0], lines[1]


# ── 首次執行（BDD @edge-case @initial-setup）───────────────────────────────

class TestFirstRun:
    def test_no_prev_snapshot_creates_v1(self, tmp_path, capsys):
        """無 api/items/v*.json（meta 亦無 version 欄位）→ changed=true、version=1、
        api/items/v1.json 含 crawled_at 與 items、api/latest.json 同內容、
        api/index.json latest_version=1 + versions[] 單一版、meta.json version=1。"""
        write_data(tmp_path, version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A],
                   counts={"CPU": 1})

        changed_line, version_line = run_main(capsys, tmp_path, tmp_path / "api")

        assert changed_line == "changed=true"
        assert version_line == "version=1"

        snapshot_file = tmp_path / "api" / "items" / "v1.json"
        assert snapshot_file.exists()
        payload = json.loads(snapshot_file.read_text(encoding="utf-8"))
        assert payload["crawled_at"] == CRAWLED_NEW
        assert payload["items"] == [ITEM_A]

        latest = json.loads((tmp_path / "api" / "latest.json").read_text(encoding="utf-8"))
        assert latest == payload

        index = json.loads((tmp_path / "api" / "index.json").read_text(encoding="utf-8"))
        assert index["latest_version"] == 1
        assert index["latest_items"] == "api/items/v1.json"
        assert index["latest"] == "api/latest.json"
        assert index["crawled_at"] == CRAWLED_NEW
        assert index["status"] == "ok"
        assert index["total"] == 1
        assert index["counts"] == {"CPU": 1}
        assert index["versions"] == [{
            "version": 1,
            "crawled_at": CRAWLED_NEW,
            "total": 1,
            "url": "api/items/v1.json",
        }]

        meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
        assert meta["version"] == 1

    def test_first_run_snapshot_uses_compact_separators(self, tmp_path, capsys):
        """api/items/v{n}.json 寫入格式：separators=(",", ":")（無多餘空白）。"""
        write_data(tmp_path, version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])
        run_main(capsys, tmp_path, tmp_path / "api")

        text = (tmp_path / "api" / "items" / "v1.json").read_text(encoding="utf-8")
        assert '"crawled_at":"' in text          # 冒號後無空白
        assert '", "items":[' not in text        # 逗號後無空白
        assert text.startswith('{"crawled_at"')

    def test_latest_uses_compact_separators(self, tmp_path, capsys):
        """api/latest.json 與版本快照同內容、同 compact 格式。"""
        write_data(tmp_path, version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])
        run_main(capsys, tmp_path, tmp_path / "api")

        text = (tmp_path / "api" / "latest.json").read_text(encoding="utf-8")
        assert text.startswith('{"crawled_at"')
        assert '"crawled_at":"' in text

    def test_meta_written_with_indent(self, tmp_path, capsys):
        """meta.json 寫入格式：indent=2。"""
        write_data(tmp_path, version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])
        run_main(capsys, tmp_path, tmp_path / "api")

        text = (tmp_path / "meta.json").read_text(encoding="utf-8")
        assert '\n  "version": 1' in text
        assert '\n  "crawled_at": "' in text


# ── 異動遞增（BDD @business-rule @cache-busting，Example 全覆蓋）────────────

class TestIncrement:
    @pytest.mark.parametrize("prev", [1, 5, 9])
    def test_changed_increments_version(self, tmp_path, capsys, prev):
        """prev 1→2 / 5→6 / 9→10：next=prev+1、寫 api/items/v{next}.json
        （含本次 crawled_at 與新 items）、latest.json 同步、index latest_version 同步、
        meta.json version 同步、舊快照不動。"""
        next_v = prev + 1
        api_dir = tmp_path / "api"
        write_snapshot(api_dir, prev, CRAWLED_OLD, [ITEM_A])
        write_data(tmp_path, version=prev, crawled_at=CRAWLED_NEW, items=[ITEM_B], changed=1)

        changed_line, version_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=true"
        assert version_line == f"version={next_v}"

        payload = json.loads((api_dir / "items" / f"v{next_v}.json").read_text(encoding="utf-8"))
        assert payload["crawled_at"] == CRAWLED_NEW
        assert payload["items"] == [ITEM_B]

        latest = json.loads((api_dir / "latest.json").read_text(encoding="utf-8"))
        assert latest == payload

        index = json.loads((api_dir / "index.json").read_text(encoding="utf-8"))
        assert index["latest_version"] == next_v
        assert index["latest_items"] == f"api/items/v{next_v}.json"

        meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
        assert meta["version"] == next_v

        # 舊快照不被覆寫
        assert json.loads((api_dir / "items" / f"v{prev}.json").read_text(encoding="utf-8"))["items"] == [ITEM_A]


class TestIndexHistory:
    def test_versions_full_history_and_changed_only_latest(self, tmp_path, capsys):
        """多版累積：index.versions[] 為完整歷史（v1/v2/v3 依版本升冪）；
        merged meta 併入 index；changed 僅最新版（v3）有，歷史版省略。"""
        api_dir = tmp_path / "api"
        write_snapshot(api_dir, 1, CRAWLED_OLD, [ITEM_A])
        write_snapshot(api_dir, 2, CRAWLED_OLD, [ITEM_B])
        write_data(tmp_path, version=2, crawled_at=CRAWLED_NEW, items=[ITEM_C],
                   total=1, counts={"CPU": 1}, changed=1)

        changed_line, version_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=true"
        assert version_line == "version=3"

        index = json.loads((api_dir / "index.json").read_text(encoding="utf-8"))
        assert index["latest_version"] == 3
        assert index["latest_items"] == "api/items/v3.json"
        assert index["crawled_at"] == CRAWLED_NEW
        assert index["total"] == 1
        assert index["counts"] == {"CPU": 1}
        assert index["status"] == "ok"
        assert [v["version"] for v in index["versions"]] == [1, 2, 3]
        assert [v["total"] for v in index["versions"]] == [1, 1, 1]
        assert [v["url"] for v in index["versions"]] == [
            "api/items/v1.json", "api/items/v2.json", "api/items/v3.json"]
        assert "changed" not in index["versions"][0]
        assert "changed" not in index["versions"][1]
        assert index["versions"][2]["changed"] == 1


# ── 無異動（BDD @business-rule @regression）────────────────────────────────

class TestNoChange:
    def test_no_change_writes_nothing(self, tmp_path, capsys):
        """items 完全一致（含 dict key 順序不同，驗證 canonical sort_keys）→
        changed=false、version 不變、data 與 api 目錄內無任何檔案新增或變更。"""
        api_dir = tmp_path / "api"
        write_snapshot(api_dir, 5, CRAWLED_OLD, [ITEM_A])
        write_data(tmp_path, version=5, crawled_at=CRAWLED_NEW, items=[ITEM_A_SHUFFLED])
        before = snapshot_all(tmp_path, api_dir)

        changed_line, version_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=false"
        assert version_line == "version=5"
        assert snapshot_all(tmp_path, api_dir) == before          # 一個 byte 都沒變
        assert not (api_dir / "items" / "v6.json").exists()

    def test_no_change_when_only_crawled_at_differs(self, tmp_path, capsys):
        """crawled_at 不同但 items 相同 → 判為無異動（時間戳不參與比對）。"""
        api_dir = tmp_path / "api"
        write_snapshot(api_dir, 3, CRAWLED_OLD, [ITEM_A])
        write_data(tmp_path, version=3, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        changed_line, version_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=false"
        assert version_line == "version=3"
        assert not (api_dir / "items" / "v4.json").exists()


# ── 目錄參數與 GITHUB_OUTPUT ────────────────────────────────────────────────

class TestCliAndOutput:
    def test_custom_data_and_api_dir_nested_path(self, tmp_path, capsys):
        """--data-dir/--api-dir 支援任意自訂路徑（巢狀目錄）。"""
        custom_data = tmp_path / "custom" / "nested" / "data"
        custom_api = tmp_path / "custom" / "nested" / "api"
        write_data(custom_data, version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        code = version_data.main(["--data-dir", str(custom_data),
                                  "--api-dir", str(custom_api)])

        assert code == 0
        assert (custom_api / "items" / "v1.json").exists()
        assert (custom_api / "index.json").exists()
        assert (custom_api / "latest.json").exists()
        assert json.loads((custom_data / "meta.json").read_text(encoding="utf-8"))["version"] == 1
        assert "changed=true" in capsys.readouterr().out

    def test_default_dirs_relative(self, tmp_path, monkeypatch, capsys):
        """未指定 --data-dir/--api-dir 時使用預設相對路徑 "data"/"api"。"""
        monkeypatch.chdir(tmp_path)
        write_data(tmp_path / "data", version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        code = version_data.main([])

        assert code == 0
        assert (tmp_path / "api" / "items" / "v1.json").exists()
        assert (tmp_path / "data" / "meta.json").exists()
        assert "version=1" in capsys.readouterr().out

    def test_github_output_written_on_change(self, tmp_path, monkeypatch, capsys):
        """GITHUB_OUTPUT 存在時以 key=value 追加寫入 changed/version 兩行（首次執行）。"""
        out_path = tmp_path / "github_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_path))
        write_data(tmp_path, version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        assert version_data.main(["--data-dir", str(tmp_path),
                                  "--api-dir", str(tmp_path / "api")]) == 0

        assert out_path.read_text(encoding="utf-8").splitlines() == ["changed=true", "version=1"]

    def test_github_output_written_on_no_change(self, tmp_path, monkeypatch, capsys):
        """GITHUB_OUTPUT 在無異動時寫 changed=false 與原版本號。"""
        out_path = tmp_path / "github_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_path))
        api_dir = tmp_path / "api"
        write_snapshot(api_dir, 5, CRAWLED_OLD, [ITEM_A])
        write_data(tmp_path, version=5, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        assert version_data.main(["--data-dir", str(tmp_path),
                                  "--api-dir", str(api_dir)]) == 0

        assert out_path.read_text(encoding="utf-8").splitlines() == ["changed=false", "version=5"]

    def test_github_output_appends_to_existing_file(self, tmp_path, monkeypatch, capsys):
        """GITHUB_OUTPUT 為追加寫入（不覆蓋既有內容）。"""
        out_path = tmp_path / "github_output.txt"
        out_path.write_text("other=1\n", encoding="utf-8")
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_path))
        write_data(tmp_path, version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        assert version_data.main(["--data-dir", str(tmp_path),
                                  "--api-dir", str(tmp_path / "api")]) == 0

        assert out_path.read_text(encoding="utf-8").splitlines() == ["other=1", "changed=true", "version=1"]

    def test_github_output_absent_writes_nothing(self, tmp_path, monkeypatch, capsys):
        """無 GITHUB_OUTPUT 環境變數 → 僅 stdout 輸出，不額外寫檔。"""
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
        write_data(tmp_path, version=None, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        assert version_data.main(["--data-dir", str(tmp_path),
                                  "--api-dir", str(tmp_path / "api")]) == 0

        files = {p.name for p in tmp_path.iterdir()}
        assert "github_output.txt" not in files
        assert "changed=true" in capsys.readouterr().out
