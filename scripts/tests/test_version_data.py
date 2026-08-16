"""version_data.py 單元測試（功能 002 §1.5 + BDD @business-rule @cache-busting、
@initial-setup、@regression）＋ AirTicketsPrice 模式（api/ 衍生 API 成品）。

涵蓋：首次執行（無 api/items/*.json → 建立 {YYYYMMDD}.json）、crawled_at 轉台北日期
（UTC+8，跨日邊界）、同日多份後綴（YYYYMMDD → YYYYMMDD_1 → YYYYMMDD_2）、
index.json 完整 files[] + merged meta + changed 僅最新檔、latest.json 穩定端點、
無異動不寫檔、crawled_at 差異不視為異動、--data-dir/--api-dir 自訂目錄、
GITHUB_OUTPUT 寫入（changed/filename）。
測試一律使用 pytest tmp_path（可 chdir），不碰真實檔案系統。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import version_data

CRAWLED_OLD = "2026-08-15T06:00:00+00:00"   # 台北 08-15 14:00 → 20260815
CRAWLED_NEW = "2026-08-16T06:00:00+00:00"   # 台北 08-16 14:00 → 20260816
CRAWLED_NEXT_DAY = "2026-08-17T06:00:00+00:00"  # 台北 08-17 → 20260817
SOURCE = "https://www.coolpc.com.tw/m/m-list.php"

# 價格相同、內容相同但 dict key 順序不同 → 驗證 canonical（sort_keys）比較
ITEM_A = {"id": "cpu-1", "category": "CPU", "name": "Intel i5-13600K", "price": 9990}
ITEM_A_SHUFFLED = {"price": 9990, "name": "Intel i5-13600K", "category": "CPU", "id": "cpu-1"}
ITEM_B = {"id": "cpu-1", "category": "CPU", "name": "Intel i5-13600K", "price": 9500}
ITEM_C = {"id": "cpu-1", "category": "CPU", "name": "Intel i5-13600K", "price": 9100}


def write_data(data_dir: Path, *, crawled_at: str,
               items: list[dict], total: int | None = None,
               counts: dict | None = None, status: str = "ok",
               changed: int | None = None) -> None:
    """寫出爬蟲 001 產物：items.json（{"meta":..., "items":[...]}）+ meta.json。
    日期制改造後 meta 不含 version 欄位。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    meta: dict = {"crawled_at": crawled_at, "source": SOURCE,
                  "total": total if total is not None else len(items),
                  "counts": counts if counts is not None else {},
                  "status": status}
    if changed is not None:
        meta["changed"] = changed
    (data_dir / "items.json").write_text(
        json.dumps({"meta": meta, "items": items}, ensure_ascii=False), encoding="utf-8")
    (data_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def write_snapshot(api_dir: Path, filename: str, crawled_at: str,
                   items: list[dict]) -> Path:
    """寫出日期制快照 api/items/{filename}.json（頂層含 crawled_at 與 items）。"""
    items_dir = api_dir / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    path = items_dir / filename
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
    """執行 main([--data-dir, --api-dir]) 並回傳 (changed 行, filename 行)。"""
    code = version_data.main(["--data-dir", str(data_dir), "--api-dir", str(api_dir)])
    out = capsys.readouterr().out
    lines = out.strip().splitlines()
    assert code == 0
    assert len(lines) == 2
    return lines[0], lines[1]


# ── 台北日期轉換（跨日邊界）────────────────────────────────────────────────

class TestTaipeiDate:
    def test_utc_to_taipei_date(self):
        """crawled_at（UTC）→ Asia/Taipei（UTC+8）日期 YYYYMMDD（含跨日邊界）。"""
        assert version_data._taipei_date("2026-08-15T15:40:00+00:00") == "20260815"  # 台北 23:40
        assert version_data._taipei_date("2026-08-15T16:30:00+00:00") == "20260816"  # 台北 00:30
        assert version_data._taipei_date("2026-08-16T06:20:49.650053+00:00") == "20260816"
        assert version_data._taipei_date("2026-08-16T06:20:49Z") == "20260816"       # Z 後綴


# ── 首次執行（BDD @edge-case @initial-setup）───────────────────────────────

class TestFirstRun:
    def test_no_prev_snapshot_creates_date_file(self, tmp_path, capsys):
        """無 api/items/*.json → changed=true、filename={date}.json、
        api/items/{date}.json 含 crawled_at 與 items、api/latest.json 同內容、
        api/index.json latest_file + files[] 單一檔、meta.json 不含 version。"""
        write_data(tmp_path, crawled_at=CRAWLED_NEW, items=[ITEM_A],
                   counts={"CPU": 1})

        changed_line, filename_line = run_main(capsys, tmp_path, tmp_path / "api")

        assert changed_line == "changed=true"
        assert filename_line == "filename=20260816.json"

        snapshot_file = tmp_path / "api" / "items" / "20260816.json"
        assert snapshot_file.exists()
        payload = json.loads(snapshot_file.read_text(encoding="utf-8"))
        assert payload["crawled_at"] == CRAWLED_NEW
        assert payload["items"] == [ITEM_A]

        latest = json.loads((tmp_path / "api" / "latest.json").read_text(encoding="utf-8"))
        assert latest == payload

        index = json.loads((tmp_path / "api" / "index.json").read_text(encoding="utf-8"))
        assert index["latest_file"] == "api/items/20260816.json"
        assert index["latest"] == "api/latest.json"
        assert index["crawled_at"] == CRAWLED_NEW
        assert index["status"] == "ok"
        assert index["total"] == 1
        assert index["counts"] == {"CPU": 1}
        assert index["files"] == [{
            "file": "20260816.json",
            "crawled_at": CRAWLED_NEW,
            "total": 1,
            "url": "api/items/20260816.json",
        }]

        meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
        assert "version" not in meta

    def test_first_run_snapshot_uses_compact_separators(self, tmp_path, capsys):
        """api/items/{date}.json 寫入格式：separators=(",", ":")（無多餘空白）。"""
        write_data(tmp_path, crawled_at=CRAWLED_NEW, items=[ITEM_A])
        run_main(capsys, tmp_path, tmp_path / "api")

        text = (tmp_path / "api" / "items" / "20260816.json").read_text(encoding="utf-8")
        assert '"crawled_at":"' in text          # 冒號後無空白
        assert '", "items":[' not in text        # 逗號後無空白
        assert text.startswith('{"crawled_at"')

    def test_latest_uses_compact_separators(self, tmp_path, capsys):
        """api/latest.json 與日期快照同內容、同 compact 格式。"""
        write_data(tmp_path, crawled_at=CRAWLED_NEW, items=[ITEM_A])
        run_main(capsys, tmp_path, tmp_path / "api")

        text = (tmp_path / "api" / "latest.json").read_text(encoding="utf-8")
        assert text.startswith('{"crawled_at"')
        assert '"crawled_at":"' in text


# ── 同日後綴 / 跨日（BDD @business-rule @cache-busting）────────────────────

class TestDateSuffix:
    def test_same_day_creates_suffix(self, tmp_path, capsys):
        """同日已有一份 → 第二份 {date}_1.json；index latest_file 指向後綴檔、
        files[] 依 (date, suffix) 升冪、changed 僅最新檔。"""
        api_dir = tmp_path / "api"
        write_snapshot(api_dir, "20260816.json", CRAWLED_NEW, [ITEM_A])
        write_data(tmp_path, crawled_at=CRAWLED_NEW, items=[ITEM_B], changed=1)

        changed_line, filename_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=true"
        assert filename_line == "filename=20260816_1.json"

        payload = json.loads((api_dir / "items" / "20260816_1.json").read_text(encoding="utf-8"))
        assert payload["crawled_at"] == CRAWLED_NEW
        assert payload["items"] == [ITEM_B]

        latest = json.loads((api_dir / "latest.json").read_text(encoding="utf-8"))
        assert latest == payload

        index = json.loads((api_dir / "index.json").read_text(encoding="utf-8"))
        assert index["latest_file"] == "api/items/20260816_1.json"
        assert [f["file"] for f in index["files"]] == ["20260816.json", "20260816_1.json"]
        assert [f["url"] for f in index["files"]] == [
            "api/items/20260816.json", "api/items/20260816_1.json"]
        assert "changed" not in index["files"][0]
        assert index["files"][1]["changed"] == 1

        # 舊快照不被覆寫
        assert json.loads((api_dir / "items" / "20260816.json").read_text(encoding="utf-8"))["items"] == [ITEM_A]

    def test_second_suffix_creates_third(self, tmp_path, capsys):
        """同日已有兩份 → 第三份 {date}_2.json。"""
        api_dir = tmp_path / "api"
        write_snapshot(api_dir, "20260816.json", CRAWLED_NEW, [ITEM_A])
        write_snapshot(api_dir, "20260816_1.json", CRAWLED_NEW, [ITEM_B])
        write_data(tmp_path, crawled_at=CRAWLED_NEW, items=[ITEM_C], changed=1)

        changed_line, filename_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=true"
        assert filename_line == "filename=20260816_2.json"
        assert (api_dir / "items" / "20260816_2.json").exists()

    def test_next_day_creates_no_suffix(self, tmp_path, capsys):
        """次日新日期 → {date}.json（無後綴）。"""
        api_dir = tmp_path / "api"
        write_snapshot(api_dir, "20260816.json", CRAWLED_NEW, [ITEM_A])
        write_data(tmp_path, crawled_at=CRAWLED_NEXT_DAY, items=[ITEM_B], changed=1)

        changed_line, filename_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=true"
        assert filename_line == "filename=20260817.json"
        assert (api_dir / "items" / "20260817.json").exists()


class TestIndexHistory:
    def test_files_full_history_and_changed_only_latest(self, tmp_path, capsys):
        """多檔累積：index.files[] 為完整日期檔清單（依 (date, suffix) 升冪）；
        merged meta 併入 index；changed 僅最新檔（20260816）有，歷史檔省略。"""
        api_dir = tmp_path / "api"
        write_snapshot(api_dir, "20260815.json", CRAWLED_OLD, [ITEM_A])
        write_snapshot(api_dir, "20260815_1.json", CRAWLED_OLD, [ITEM_B])
        write_data(tmp_path, crawled_at=CRAWLED_NEW, items=[ITEM_C],
                   total=1, counts={"CPU": 1}, changed=1)

        changed_line, filename_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=true"
        assert filename_line == "filename=20260816.json"

        index = json.loads((api_dir / "index.json").read_text(encoding="utf-8"))
        assert index["latest_file"] == "api/items/20260816.json"
        assert index["crawled_at"] == CRAWLED_NEW
        assert index["total"] == 1
        assert index["counts"] == {"CPU": 1}
        assert index["status"] == "ok"
        assert [f["file"] for f in index["files"]] == [
            "20260815.json", "20260815_1.json", "20260816.json"]
        assert [f["total"] for f in index["files"]] == [1, 1, 1]
        assert [f["url"] for f in index["files"]] == [
            "api/items/20260815.json", "api/items/20260815_1.json",
            "api/items/20260816.json"]
        assert "changed" not in index["files"][0]
        assert "changed" not in index["files"][1]
        assert index["files"][2]["changed"] == 1


# ── 無異動（BDD @business-rule @regression）────────────────────────────────

class TestNoChange:
    def test_no_change_writes_nothing(self, tmp_path, capsys):
        """items 完全一致（含 dict key 順序不同，驗證 canonical sort_keys）→
        changed=false、filename 為空、data 與 api 目錄內無任何檔案新增或變更。"""
        api_dir = tmp_path / "api"
        write_snapshot(api_dir, "20260816.json", CRAWLED_OLD, [ITEM_A])
        write_data(tmp_path, crawled_at=CRAWLED_NEW, items=[ITEM_A_SHUFFLED])
        before = snapshot_all(tmp_path, api_dir)

        changed_line, filename_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=false"
        assert filename_line == "filename="
        assert snapshot_all(tmp_path, api_dir) == before          # 一個 byte 都沒變
        assert not (api_dir / "items" / "20260816_1.json").exists()

    def test_no_change_when_only_crawled_at_differs(self, tmp_path, capsys):
        """crawled_at 不同但 items 相同 → 判為無異動（時間戳不參與比對）。"""
        api_dir = tmp_path / "api"
        write_snapshot(api_dir, "20260816.json", CRAWLED_OLD, [ITEM_A])
        write_data(tmp_path, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        changed_line, filename_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=false"
        assert filename_line == "filename="
        assert not (api_dir / "items" / "20260817.json").exists()


# ── 目錄參數與 GITHUB_OUTPUT ────────────────────────────────────────────────

class TestCliAndOutput:
    def test_custom_data_and_api_dir_nested_path(self, tmp_path, capsys):
        """--data-dir/--api-dir 支援任意自訂路徑（巢狀目錄）。"""
        custom_data = tmp_path / "custom" / "nested" / "data"
        custom_api = tmp_path / "custom" / "nested" / "api"
        write_data(custom_data, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        code = version_data.main(["--data-dir", str(custom_data),
                                  "--api-dir", str(custom_api)])

        assert code == 0
        assert (custom_api / "items" / "20260816.json").exists()
        assert (custom_api / "index.json").exists()
        assert (custom_api / "latest.json").exists()
        assert "changed=true" in capsys.readouterr().out

    def test_default_dirs_relative(self, tmp_path, monkeypatch, capsys):
        """未指定 --data-dir/--api-dir 時使用預設相對路徑 "data"/"api"。"""
        monkeypatch.chdir(tmp_path)
        write_data(tmp_path / "data", crawled_at=CRAWLED_NEW, items=[ITEM_A])

        code = version_data.main([])

        assert code == 0
        assert (tmp_path / "api" / "items" / "20260816.json").exists()
        assert (tmp_path / "data" / "meta.json").exists()
        assert "filename=20260816.json" in capsys.readouterr().out

    def test_github_output_written_on_change(self, tmp_path, monkeypatch, capsys):
        """GITHUB_OUTPUT 存在時以 key=value 追加寫入 changed/filename 兩行（首次執行）。"""
        out_path = tmp_path / "github_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_path))
        write_data(tmp_path, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        assert version_data.main(["--data-dir", str(tmp_path),
                                  "--api-dir", str(tmp_path / "api")]) == 0

        assert out_path.read_text(encoding="utf-8").splitlines() == [
            "changed=true", "filename=20260816.json"]

    def test_github_output_written_on_no_change(self, tmp_path, monkeypatch, capsys):
        """GITHUB_OUTPUT 在無異動時寫 changed=false 與空 filename。"""
        out_path = tmp_path / "github_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_path))
        api_dir = tmp_path / "api"
        write_snapshot(api_dir, "20260816.json", CRAWLED_OLD, [ITEM_A])
        write_data(tmp_path, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        assert version_data.main(["--data-dir", str(tmp_path),
                                  "--api-dir", str(api_dir)]) == 0

        assert out_path.read_text(encoding="utf-8").splitlines() == ["changed=false", "filename="]

    def test_github_output_appends_to_existing_file(self, tmp_path, monkeypatch, capsys):
        """GITHUB_OUTPUT 為追加寫入（不覆蓋既有內容）。"""
        out_path = tmp_path / "github_output.txt"
        out_path.write_text("other=1\n", encoding="utf-8")
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_path))
        write_data(tmp_path, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        assert version_data.main(["--data-dir", str(tmp_path),
                                  "--api-dir", str(tmp_path / "api")]) == 0

        assert out_path.read_text(encoding="utf-8").splitlines() == [
            "other=1", "changed=true", "filename=20260816.json"]

    def test_github_output_absent_writes_nothing(self, tmp_path, monkeypatch, capsys):
        """無 GITHUB_OUTPUT 環境變數 → 僅 stdout 輸出，不額外寫檔。"""
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
        write_data(tmp_path, crawled_at=CRAWLED_NEW, items=[ITEM_A])

        assert version_data.main(["--data-dir", str(tmp_path),
                                  "--api-dir", str(tmp_path / "api")]) == 0

        files = {p.name for p in tmp_path.iterdir()}
        assert "github_output.txt" not in files
        assert "changed=true" in capsys.readouterr().out
