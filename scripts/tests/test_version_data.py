"""version_data.py 單元測試（契約 v2：對外層依分類切檔）。

涵蓋：data/items/{g}.json（純 items 陣列）→ api/items/{g}.json 鏡像
（同內容、compact、g 由檔名繼承、僅寫異動分類、殘留檔不刪）、api/daily 鏡像
（byte 一致、有新增/更新才寫、殘留檔不刪）、api/trends/{id}.json 聚合
（依日期升冪、多檔合併、全量重建冪等）、api/index.json（categories[] =
[{id, name, file, count}]——id=g、name 依 G→name 唯讀對照、count=該檔 items 數；
daily_files[] 依檔名升冪含 records、trends_prefix、**不含 latest_file/latest**）、
不再產生 api/latest.json、防線（meta.status == "failed" 或 total == 0 → 不寫任何
檔案）、無異動不寫檔（daily 無新檔 + 全部分類 canonical 相同 → 檔案零變動；
crawled_at 差異不視為異動）、異動觸發（新 daily 檔 / 任一分類檔異動）、
遷移相容（舊單檔 data/items.json → 依 category 拆出 data/items/{g}.json 並印警告；
data/items/ 存在時不觸發；防線觸發時連遷移都不做）、
--data-dir/--api-dir 自訂目錄、GITHUB_OUTPUT 寫入（changed/filename）。
測試一律使用 pytest tmp_path（可 chdir），不碰真實檔案系統。
"""
from __future__ import annotations

import json
from pathlib import Path

import version_data

CRAWLED_OLD = "2026-08-15T06:00:00+00:00"   # 台北 08-15 14:00
CRAWLED_NEW = "2026-08-16T06:00:00+00:00"   # 台北 08-16 14:00
CRAWLED_NEXT_DAY = "2026-08-17T06:00:00+00:00"  # 台北 08-17 14:00
SOURCE = "https://www.coolpc.com.tw/m/m-list.php"

# data/items/{g}.json 的 items 為純物件（無 category 欄位、無 meta）
ITEM_A = {"id": "cpu-1", "name": "Intel i5-13600K", "price": 9990,
          "status": "in_stock", "first_seen": "2026-08-15", "last_seen": "2026-08-16",
          "history": [["2026-08-15", 9990], ["2026-08-16", 9990]]}
# 內容相同但 dict key 順序不同 → 驗證 canonical（sort_keys）比較
ITEM_A_SHUFFLED = {"history": [["2026-08-15", 9990], ["2026-08-16", 9990]],
                   "status": "in_stock", "price": 9990, "name": "Intel i5-13600K",
                   "last_seen": "2026-08-16", "first_seen": "2026-08-15",
                   "id": "cpu-1"}
ITEM_B = {**ITEM_A, "price": 9500}  # 同日價變（history 末點對齊最新價）
ITEM_GPU = {"id": "gpu-1", "name": "RTX 4070", "price": 19990,
            "status": "in_stock", "first_seen": "2026-08-15", "last_seen": "2026-08-16",
            "history": [["2026-08-15", 19990], ["2026-08-16", 19990]]}

# 分類檔真相層：{g: [items]}（g = G 索引，依檔名繼承）
CATS = {"g4": [ITEM_A], "g12": [ITEM_GPU]}

# 每日價格點（data/daily/YYYYMMDD.json 的 {id: price}）
DAILY_15 = {"cpu-1": 9990, "gpu-1": 19990}
DAILY_16 = {"cpu-1": 9990, "gpu-1": 19990}  # 平價日
DAILY_17 = {"cpu-1": 9500, "gpu-1": 18990}


def write_data(data_dir: Path, *, crawled_at: str,
               categories: dict[str, list] | None = None,
               legacy: dict[str, list] | None = None,
               total: int | None = None, counts: dict | None = None,
               status: str = "ok", changed: int | None = None,
               daily: dict[str, dict[str, int]] | None = None) -> None:
    """寫出爬蟲產物：data/meta.json + data/items/{g}.json（契約 v2）或舊單檔。

    - categories: {g: [items]} → data/items/{g}.json（純 items 陣列）
    - legacy: {category_name: [items]} → 舊單檔 data/items.json（items 含 category
      欄位，供遷移相容測試）；給定時不寫 data/items/
    - daily: {filename: {id: price}} → data/daily/*.json"""
    data_dir.mkdir(parents=True, exist_ok=True)
    if legacy is not None:
        items = [dict(item, category=cat)
                 for cat, payload in legacy.items() for item in payload]
    else:
        items = [item for payload in (categories or {}).values() for item in payload]
    meta: dict = {"crawled_at": crawled_at, "source": SOURCE,
                  "total": total if total is not None else len(items),
                  "counts": counts if counts is not None else {},
                  "status": status}
    if changed is not None:
        meta["changed"] = changed
    (data_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    if legacy is not None:
        (data_dir / "items.json").write_text(
            json.dumps({"meta": meta, "items": items}, ensure_ascii=False),
            encoding="utf-8")
    else:
        items_dir = data_dir / "items"
        items_dir.mkdir(parents=True, exist_ok=True)
        for g, payload in (categories or {}).items():
            (items_dir / f"{g}.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    if daily:
        (data_dir / "daily").mkdir(parents=True, exist_ok=True)
        for name, prices in daily.items():
            (data_dir / "daily" / name).write_text(
                json.dumps(prices, ensure_ascii=False), encoding="utf-8")


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
    """執行 main([--data-dir, --api-dir]) 並回傳 (changed 行, filename 行)。

    僅適用於 stdout 恰好兩行的情境（遷移測試另以 readouterr() 直接檢查 stderr）。"""
    code = version_data.main(["--data-dir", str(data_dir), "--api-dir", str(api_dir)])
    out = capsys.readouterr().out
    lines = out.strip().splitlines()
    assert code == 0
    assert len(lines) == 2
    return lines[0], lines[1]


# ── api/items/{g}.json 鏡像（同內容、compact、g 由檔名繼承）─────────────────

class TestApiItems:
    def test_first_run_creates_category_files_items_asis(self, tmp_path, capsys):
        """首次執行（無 api/）→ changed=true、filename=最新 daily 檔名；
        api/items/{g}.json = data/items/{g} 內容原樣（純 items 陣列，零轉換）。"""
        write_data(tmp_path, crawled_at=CRAWLED_NEW,
                   categories={"g4": [ITEM_A], "g12": [ITEM_GPU]},
                   counts={"CPU": 1, "顯示卡": 1}, daily={"20260816.json": DAILY_16})

        changed_line, filename_line = run_main(capsys, tmp_path, tmp_path / "api")

        assert changed_line == "changed=true"
        assert filename_line == "filename=20260816.json"

        cpu = json.loads((tmp_path / "api" / "items" / "g4.json").read_text(encoding="utf-8"))
        assert cpu == [ITEM_A]
        gpu = json.loads((tmp_path / "api" / "items" / "g12.json").read_text(encoding="utf-8"))
        assert gpu == [ITEM_GPU]

    def test_category_files_use_compact_separators(self, tmp_path, capsys):
        """api/items/{g}.json 寫入格式：separators=(",", ":")、純陣列（無 category/meta）。"""
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories={"g4": [ITEM_A]},
                   daily={"20260816.json": DAILY_16})
        run_main(capsys, tmp_path, tmp_path / "api")

        text = (tmp_path / "api" / "items" / "g4.json").read_text(encoding="utf-8")
        assert text.startswith("[")            # 純 items 陣列
        assert '", "' not in text              # 逗號後無空白
        assert '": "' not in text              # 冒號後無空白
        assert '"category"' not in text        # 無 category 欄位
        assert '"meta"' not in text            # 無 meta

    def test_writes_only_changed_category_files(self, tmp_path, capsys):
        """兩分類只改其一 → 只重寫該分類檔（另一分類檔案內容不變）。"""
        api_dir = tmp_path / "api"
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})
        run_main(capsys, tmp_path, api_dir)
        gpu_before = (api_dir / "items" / "g12.json").read_bytes()

        write_data(tmp_path, crawled_at=CRAWLED_NEW,
                   categories={"g4": [ITEM_B], "g12": [ITEM_GPU]},
                   daily={"20260816.json": DAILY_16})
        run_main(capsys, tmp_path, api_dir)

        assert json.loads((api_dir / "items" / "g4.json").read_text(encoding="utf-8")) == [ITEM_B]
        assert (api_dir / "items" / "g12.json").read_bytes() == gpu_before

    def test_stale_api_items_left_untouched(self, tmp_path, capsys):
        """api/items/ 中的殘留檔（data/items 已無）不刪除：契約只要求鏡像新增/更新。"""
        api_dir = tmp_path / "api"
        (api_dir / "items").mkdir(parents=True)
        stale = api_dir / "items" / "20260814.json"
        stale.write_text('[{"id": "old"}]', encoding="utf-8")
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories={"g4": [ITEM_A]},
                   daily={"20260816.json": DAILY_16})

        run_main(capsys, tmp_path, api_dir)

        assert stale.read_text(encoding="utf-8") == '[{"id": "old"}]'


# ── api/daily 鏡像（不變）──────────────────────────────────────────────────

class TestDailyMirror:
    def test_mirrors_all_data_daily_byte_identical(self, tmp_path, capsys):
        """api/daily 鏡像 data/daily：同名檔、內容 byte 一致。"""
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260815.json": DAILY_15, "20260816.json": DAILY_16})
        run_main(capsys, tmp_path, tmp_path / "api")

        for name in ("20260815.json", "20260816.json"):
            dest = tmp_path / "api" / "daily" / name
            assert dest.exists()
            assert dest.read_bytes() == (tmp_path / "daily" / name).read_bytes()

    def test_updated_daily_content_overwrites(self, tmp_path, capsys):
        """data/daily 內容更新（同日價變）→ 重跑覆寫 api/daily 對應檔。"""
        api_dir = tmp_path / "api"
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})
        run_main(capsys, tmp_path, api_dir)

        write_data(tmp_path, crawled_at=CRAWLED_NEW,
                   categories={"g4": [ITEM_B], "g12": [ITEM_GPU]},  # 分類檔同步異動（內容更新必然隨價格異動）
                   daily={"20260816.json": DAILY_17})  # 同檔名、內容更新
        changed_line, _ = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=true"
        dest = api_dir / "daily" / "20260816.json"
        assert dest.read_bytes() == (tmp_path / "daily" / "20260816.json").read_bytes()

    def test_stale_api_daily_left_untouched(self, tmp_path, capsys):
        """api/daily 中的殘留檔（data/daily 已無）不刪除：契約只要求鏡像新增/更新。"""
        api_dir = tmp_path / "api"
        (api_dir / "daily").mkdir(parents=True)
        stale = api_dir / "daily" / "20260814.json"
        stale.write_text('{"cpu-1": 10000}', encoding="utf-8")
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})

        run_main(capsys, tmp_path, api_dir)

        assert stale.read_text(encoding="utf-8") == '{"cpu-1": 10000}'


# ── api/trends/{item_id}.json 聚合（不變）──────────────────────────────────

class TestTrends:
    def test_aggregates_all_daily_sorted_asc(self, tmp_path, capsys):
        """trends 聚合所有 data/daily 檔：{"id","history":[[d,p],...]}，依日期升冪。"""
        write_data(tmp_path, crawled_at=CRAWLED_NEXT_DAY, categories=CATS,
                   daily={"20260815.json": DAILY_15, "20260816.json": DAILY_16,
                          "20260817.json": DAILY_17})
        run_main(capsys, tmp_path, tmp_path / "api")

        cpu = json.loads((tmp_path / "api" / "trends" / "cpu-1.json").read_text(encoding="utf-8"))
        assert cpu == {"id": "cpu-1", "history": [
            ["2026-08-15", 9990], ["2026-08-16", 9990], ["2026-08-17", 9500]]}
        gpu = json.loads((tmp_path / "api" / "trends" / "gpu-1.json").read_text(encoding="utf-8"))
        assert gpu == {"id": "gpu-1", "history": [
            ["2026-08-15", 19990], ["2026-08-16", 19990], ["2026-08-17", 18990]]}

    def test_rebuild_is_idempotent_under_items_change(self, tmp_path, capsys):
        """daily 檔不變、僅 items 異動 → changed=true 且 trends 全量重建輸出不變
        （全量重建冪等：同輸入 → 同輸出）。"""
        api_dir = tmp_path / "api"
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})
        run_main(capsys, tmp_path, api_dir)
        before = (api_dir / "trends" / "cpu-1.json").read_bytes()

        write_data(tmp_path, crawled_at=CRAWLED_NEW,
                   categories={"g4": [ITEM_B], "g12": [ITEM_GPU]},
                   daily={"20260816.json": DAILY_16})
        changed_line, _ = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=true"
        assert (api_dir / "trends" / "cpu-1.json").read_bytes() == before

    def test_no_daily_files_no_trends_dir(self, tmp_path, capsys):
        """data/daily 為空 → 不建立 api/trends/（無從聚合）。"""
        api_dir = tmp_path / "api"
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS)

        run_main(capsys, tmp_path, api_dir)

        assert not (api_dir / "trends").exists()
        assert not (api_dir / "daily").exists()


# ── api/index.json（categories[]；無 latest/latest_file）───────────────────

class TestIndex:
    def test_index_shape_categories_and_daily_files_sorted(self, tmp_path, capsys):
        """index shape：categories[] = [{id,name,file,count}]（id=g、name 依 G→name
        對照、依 G 數值序，與寫入順序無關）、daily_files[] 依檔名升冪含 records、
        trends_prefix、merged meta、**不含 latest_file/latest**。"""
        write_data(tmp_path, crawled_at=CRAWLED_NEXT_DAY,
                   categories={"g12": [ITEM_GPU], "g4": [ITEM_A]},  # 亂序寫入 → 輸出仍升冪
                   total=2, counts={"CPU": 1, "顯示卡": 1},
                   daily={"20260817.json": DAILY_17,      # 亂序寫入 → 輸出仍升冪
                          "20260816.json": DAILY_16,
                          "20260815.json": DAILY_15})
        run_main(capsys, tmp_path, tmp_path / "api")

        index = json.loads((tmp_path / "api" / "index.json").read_text(encoding="utf-8"))
        assert "latest_file" not in index
        assert "latest" not in index
        assert index["trends_prefix"] == "api/trends/"
        assert index["crawled_at"] == CRAWLED_NEXT_DAY
        assert index["status"] == "ok"
        assert index["total"] == 2
        assert index["counts"] == {"CPU": 1, "顯示卡": 1}
        assert index["source"] == SOURCE
        assert index["description"] == version_data.DESCRIPTION
        assert index["categories"] == [
            {"id": "g4", "name": "CPU", "file": "api/items/g4.json", "count": 1},
            {"id": "g12", "name": "顯示卡", "file": "api/items/g12.json", "count": 1},
        ]
        assert index["daily_files"] == [
            {"file": "20260815.json", "url": "api/daily/20260815.json", "records": 2},
            {"file": "20260816.json", "url": "api/daily/20260816.json", "records": 2},
            {"file": "20260817.json", "url": "api/daily/20260817.json", "records": 2},
        ]
        assert "generated_at" in index

    def test_category_count_is_payload_length(self, tmp_path, capsys):
        """categories[].count = 該分類檔 items 陣列長度（非 meta.counts 值）。"""
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories={"g4": [ITEM_A, ITEM_B]},
                   counts={"CPU": 99}, daily={"20260816.json": DAILY_16})
        run_main(capsys, tmp_path, tmp_path / "api")

        index = json.loads((tmp_path / "api" / "index.json").read_text(encoding="utf-8"))
        assert index["categories"] == [
            {"id": "g4", "name": "CPU", "file": "api/items/g4.json", "count": 2}]

    def test_unknown_g_stem_falls_back_to_stem_name(self, tmp_path, capsys):
        """檔名非已知 G 索引（G→name 對照查無）→ name 直接取檔名 stem。"""
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories={"自訂區": [ITEM_A]},
                   daily={"20260816.json": DAILY_16})
        run_main(capsys, tmp_path, tmp_path / "api")

        index = json.loads((tmp_path / "api" / "index.json").read_text(encoding="utf-8"))
        assert index["categories"] == [
            {"id": "自訂區", "name": "自訂區", "file": "api/items/自訂區.json", "count": 1}]


# ── 不再產生單一 api/latest.json ───────────────────────────────────────────

class TestNoLatestJson:
    def test_no_latest_json_created(self, tmp_path, capsys):
        """契約 v2：不再產生單一 api/latest.json（由 api/items/{g} 取代）。"""
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})
        run_main(capsys, tmp_path, tmp_path / "api")

        assert not (tmp_path / "api" / "latest.json").exists()
        assert (tmp_path / "api" / "items" / "g4.json").exists()

    def test_stale_latest_json_not_deleted(self, tmp_path, capsys):
        """既有 api/latest.json 殘留檔不刪（本模組只做新增/更新，不做清理）。"""
        api_dir = tmp_path / "api"
        api_dir.mkdir(parents=True)
        stale = api_dir / "latest.json"
        stale.write_text('{"items": []}', encoding="utf-8")
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})

        run_main(capsys, tmp_path, api_dir)

        assert stale.exists()


# ── 防線（meta.status == "failed" / total == 0 → 不寫任何檔案）──────────────

class TestGuardRail:
    def test_failed_status_writes_nothing(self, tmp_path, capsys):
        """meta.status == "failed" → changed=false、filename 空、data 與 api 全部
        檔案一個 byte 都不變（含既有 items/daily/trends/index 不被覆寫）。"""
        api_dir = tmp_path / "api"
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})
        run_main(capsys, tmp_path, api_dir)  # 先正常建一次

        write_data(tmp_path, crawled_at=CRAWLED_NEXT_DAY, categories=CATS,
                   daily={"20260817.json": DAILY_17}, status="failed")
        before = snapshot_all(tmp_path, api_dir)
        changed_line, filename_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=false"
        assert filename_line == "filename="
        assert snapshot_all(tmp_path, api_dir) == before

    def test_failed_status_first_run_creates_nothing(self, tmp_path, capsys):
        """首次執行即 failed（無既有 api/）→ 不建立 api/ 任何檔案。"""
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS, status="failed",
                   daily={"20260816.json": DAILY_16})

        changed_line, filename_line = run_main(capsys, tmp_path, tmp_path / "api")

        assert changed_line == "changed=false"
        assert filename_line == "filename="
        assert not (tmp_path / "api").exists()          # 未建立任何檔案

    def test_zero_total_writes_nothing(self, tmp_path, capsys):
        """meta.total == 0 → changed=false、不寫任何檔案
        （防人工手術壞資料覆寫好對外成品）。"""
        api_dir = tmp_path / "api"
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})
        run_main(capsys, tmp_path, api_dir)

        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS, total=0, status="ok",
                   daily={"20260817.json": DAILY_17})
        before = snapshot_all(tmp_path, api_dir)
        changed_line, filename_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=false"
        assert filename_line == "filename="
        assert snapshot_all(tmp_path, api_dir) == before


# ── 無異動（BDD @business-rule @regression）────────────────────────────────

class TestNoChange:
    def test_same_items_and_no_new_daily_writes_nothing(self, tmp_path, capsys):
        """任一分類 canonical 相同（含 key 順序不同）且 daily 無新檔 → changed=false、
        filename=最新 daily 檔名、data 與 api 目錄內無任何檔案新增或變更。"""
        api_dir = tmp_path / "api"
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})
        run_main(capsys, tmp_path, api_dir)  # 建立 api/

        write_data(tmp_path, crawled_at=CRAWLED_NEW,
                   categories={"g4": [ITEM_A_SHUFFLED], "g12": [ITEM_GPU]},
                   daily={"20260816.json": DAILY_16})
        before = snapshot_all(tmp_path, api_dir)
        changed_line, filename_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=false"
        assert filename_line == "filename=20260816.json"
        assert snapshot_all(tmp_path, api_dir) == before   # 一個 byte 都沒變

    def test_no_change_when_only_crawled_at_differs(self, tmp_path, capsys):
        """crawled_at 不同但分類檔相同、daily 無新檔 → 判為無異動
        （時間戳不參與比對；api/items 不被覆寫）。"""
        api_dir = tmp_path / "api"
        write_data(tmp_path, crawled_at=CRAWLED_OLD, categories=CATS,
                   daily={"20260816.json": DAILY_16})
        run_main(capsys, tmp_path, api_dir)
        before = snapshot_all(tmp_path, api_dir)

        write_data(tmp_path, crawled_at=CRAWLED_NEXT_DAY, categories=CATS,
                   daily={"20260816.json": DAILY_16})
        before = snapshot_all(tmp_path, api_dir)
        changed_line, filename_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=false"
        assert filename_line == "filename=20260816.json"
        assert snapshot_all(tmp_path, api_dir) == before


# ── 異動觸發（新 daily 檔 / 分類檔異動）────────────────────────────────────

class TestChangedTriggers:
    def test_new_daily_file_triggers_change(self, tmp_path, capsys):
        """分類檔相同但 data/daily 出現新檔 → changed=true（跨日）；api/items
        內容不變、index 的 crawled_at 隨 meta 前進。"""
        api_dir = tmp_path / "api"
        write_data(tmp_path, crawled_at=CRAWLED_OLD, categories=CATS,
                   daily={"20260816.json": DAILY_16})
        run_main(capsys, tmp_path, api_dir)

        write_data(tmp_path, crawled_at=CRAWLED_NEXT_DAY, categories=CATS,
                   daily={"20260816.json": DAILY_16, "20260817.json": DAILY_17})
        changed_line, filename_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=true"
        assert filename_line == "filename=20260817.json"
        assert (api_dir / "daily" / "20260817.json").exists()
        assert (api_dir / "trends" / "cpu-1.json").exists()
        assert json.loads((api_dir / "items" / "g4.json").read_text(encoding="utf-8")) == [ITEM_A]
        index = json.loads((api_dir / "index.json").read_text(encoding="utf-8"))
        assert index["crawled_at"] == CRAWLED_NEXT_DAY
        assert index["categories"][0]["id"] == "g4"

    def test_items_change_in_category_triggers_change(self, tmp_path, capsys):
        """daily 無新檔但任一分類檔異動（同日價變）→ changed=true。"""
        api_dir = tmp_path / "api"
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})
        run_main(capsys, tmp_path, api_dir)

        write_data(tmp_path, crawled_at=CRAWLED_NEW,
                   categories={"g4": [ITEM_B], "g12": [ITEM_GPU]},
                   daily={"20260816.json": DAILY_16})
        changed_line, _ = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=true"
        assert json.loads((api_dir / "items" / "g4.json").read_text(encoding="utf-8")) == [ITEM_B]

    def test_no_daily_files_but_items_change(self, tmp_path, capsys):
        """data/daily 為空但分類檔異動 → changed=true、filename 空。"""
        api_dir = tmp_path / "api"
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS)
        run_main(capsys, tmp_path, api_dir)

        write_data(tmp_path, crawled_at=CRAWLED_NEXT_DAY,
                   categories={"g4": [ITEM_B], "g12": [ITEM_GPU]})
        changed_line, filename_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=true"
        assert filename_line == "filename="


# ── 遷移相容（舊單檔 data/items.json → data/items/{g}.json）────────────────

class TestMigration:
    def test_legacy_single_file_split_by_category(self, tmp_path, capsys):
        """data/items.json（舊單檔，items 含 category 欄位）仍在、data/items/ 不存在
        → 依 category 拆出寫入 data/items/{g}.json（純 items 陣列、無 category/meta），
        stderr 印警告；後續 api/items 鏡像 + index.categories 用對應 G 索引與中文名。"""
        write_data(tmp_path, crawled_at=CRAWLED_NEW,
                   legacy={"CPU": [ITEM_A], "主機板": [ITEM_GPU]},
                   counts={"CPU": 1, "主機板": 1}, daily={"20260816.json": DAILY_16})

        code = version_data.main(["--data-dir", str(tmp_path),
                                  "--api-dir", str(tmp_path / "api")])
        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()

        assert code == 0
        assert lines == ["changed=true", "filename=20260816.json"]
        assert "警告" in captured.err and "data/items" in captured.err

        cpu = json.loads((tmp_path / "items" / "g4.json").read_text(encoding="utf-8"))
        assert cpu == [ITEM_A]     # 已移除 category 欄位
        mobo = json.loads((tmp_path / "items" / "g5.json").read_text(encoding="utf-8"))
        assert mobo == [ITEM_GPU]

        index = json.loads((tmp_path / "api" / "index.json").read_text(encoding="utf-8"))
        assert index["categories"] == [
            {"id": "g4", "name": "CPU", "file": "api/items/g4.json", "count": 1},
            {"id": "g5", "name": "主機板", "file": "api/items/g5.json", "count": 1},
        ]

    def test_legacy_unknown_category_uses_safe_g(self, tmp_path, capsys):
        """舊單檔含未列於 G→name 對照的分類名 → 以檔名安全化字串為 g（"/" → "-"）。"""
        write_data(tmp_path, crawled_at=CRAWLED_NEW, legacy={"新分類/X": [ITEM_A]},
                   daily={"20260816.json": DAILY_16})

        code = version_data.main(["--data-dir", str(tmp_path),
                                  "--api-dir", str(tmp_path / "api")])
        capsys.readouterr()

        assert code == 0
        assert (tmp_path / "items" / "g新分類-X.json").exists()
        index = json.loads((tmp_path / "api" / "index.json").read_text(encoding="utf-8"))
        assert index["categories"] == [
            {"id": "g新分類-X", "name": "g新分類-X", "file": "api/items/g新分類-X.json",
             "count": 1}]

    def test_migration_skipped_when_items_dir_exists(self, tmp_path, capsys):
        """data/items/ 已存在（契約 v2 真相層）→ 不遷移、不印警告，以分類檔為準
        （即使 data/items.json 舊單檔仍在，也不理會）。"""
        write_data(tmp_path, crawled_at=CRAWLED_NEW, legacy={"CPU": [ITEM_A]},
                   daily={"20260816.json": DAILY_16})
        # 手工建立 data/items/（模擬爬蟲已切檔）——內容與舊單檔不同
        (tmp_path / "items").mkdir(parents=True)
        (tmp_path / "items" / "g4.json").write_text(
            json.dumps([ITEM_B], ensure_ascii=False), encoding="utf-8")

        code = version_data.main(["--data-dir", str(tmp_path),
                                  "--api-dir", str(tmp_path / "api")])
        captured = capsys.readouterr()

        assert code == 0
        assert "警告" not in captured.err
        assert captured.out.strip().splitlines() == ["changed=true", "filename=20260816.json"]
        assert json.loads((tmp_path / "api" / "items" / "g4.json").read_text(
            encoding="utf-8")) == [ITEM_B]

    def test_migration_not_run_when_guard_rail_fires(self, tmp_path, capsys):
        """防線觸發（failed / total==0）→ 連遷移寫入 data/items/ 都不執行。"""
        api_dir = tmp_path / "api"
        write_data(tmp_path, crawled_at=CRAWLED_NEW, legacy={"CPU": [ITEM_A]},
                   status="failed", daily={"20260816.json": DAILY_16})

        changed_line, filename_line = run_main(capsys, tmp_path, api_dir)

        assert changed_line == "changed=false"
        assert filename_line == "filename="
        assert not (tmp_path / "items").exists()   # 未遷移、未拆檔
        assert not api_dir.exists()                          # 未建立 api/


# ── 目錄參數與 GITHUB_OUTPUT（輸出格式維持 v1）─────────────────────────────

class TestCliAndOutput:
    def test_custom_data_and_api_dir_nested_path(self, tmp_path, capsys):
        """--data-dir/--api-dir 支援任意自訂路徑（巢狀目錄）。"""
        custom_data = tmp_path / "custom" / "nested" / "data"
        custom_api = tmp_path / "custom" / "nested" / "api"
        write_data(custom_data, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})

        code = version_data.main(["--data-dir", str(custom_data),
                                  "--api-dir", str(custom_api)])

        assert code == 0
        assert (custom_api / "items" / "g4.json").exists()
        assert (custom_api / "daily" / "20260816.json").exists()
        assert (custom_api / "trends" / "cpu-1.json").exists()
        assert (custom_api / "index.json").exists()
        assert "changed=true" in capsys.readouterr().out

    def test_default_dirs_relative(self, tmp_path, monkeypatch, capsys):
        """未指定 --data-dir/--api-dir 時使用預設相對路徑 "data"/"api"。"""
        monkeypatch.chdir(tmp_path)
        write_data(tmp_path / "data", crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})

        code = version_data.main([])

        assert code == 0
        assert (tmp_path / "api" / "items" / "g4.json").exists()
        assert (tmp_path / "api" / "daily" / "20260816.json").exists()
        assert (tmp_path / "data" / "meta.json").exists()
        assert "filename=20260816.json" in capsys.readouterr().out

    def test_github_output_written_on_change(self, tmp_path, monkeypatch, capsys):
        """GITHUB_OUTPUT 存在時以 key=value 追加寫入 changed/filename 兩行（首次執行）。"""
        out_path = tmp_path / "github_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_path))
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})

        assert version_data.main(["--data-dir", str(tmp_path),
                                  "--api-dir", str(tmp_path / "api")]) == 0

        assert out_path.read_text(encoding="utf-8").splitlines() == [
            "changed=true", "filename=20260816.json"]

    def test_github_output_written_on_no_change(self, tmp_path, monkeypatch, capsys):
        """GITHUB_OUTPUT 在無異動時寫 changed=false 與最新 daily 檔名。"""
        out_path = tmp_path / "github_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_path))
        api_dir = tmp_path / "api"
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})
        version_data.main(["--data-dir", str(tmp_path), "--api-dir", str(api_dir)])
        out_path.write_text("", encoding="utf-8")  # 清掉首次寫入

        write_data(tmp_path, crawled_at=CRAWLED_NEXT_DAY, categories=CATS,
                   daily={"20260816.json": DAILY_16})
        assert version_data.main(["--data-dir", str(tmp_path),
                                  "--api-dir", str(api_dir)]) == 0

        assert out_path.read_text(encoding="utf-8").splitlines() == [
            "changed=false", "filename=20260816.json"]

    def test_github_output_appends_to_existing_file(self, tmp_path, monkeypatch, capsys):
        """GITHUB_OUTPUT 為追加寫入（不覆蓋既有內容）。"""
        out_path = tmp_path / "github_output.txt"
        out_path.write_text("other=1\n", encoding="utf-8")
        monkeypatch.setenv("GITHUB_OUTPUT", str(out_path))
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})

        assert version_data.main(["--data-dir", str(tmp_path),
                                  "--api-dir", str(tmp_path / "api")]) == 0

        assert out_path.read_text(encoding="utf-8").splitlines() == [
            "other=1", "changed=true", "filename=20260816.json"]

    def test_github_output_absent_writes_nothing(self, tmp_path, monkeypatch, capsys):
        """無 GITHUB_OUTPUT 環境變數 → 僅 stdout 輸出，不額外寫檔。"""
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
        write_data(tmp_path, crawled_at=CRAWLED_NEW, categories=CATS,
                   daily={"20260816.json": DAILY_16})

        assert version_data.main(["--data-dir", str(tmp_path),
                                  "--api-dir", str(tmp_path / "api")]) == 0

        files = {p.name for p in tmp_path.iterdir()}
        assert "github_output.txt" not in files
        assert "changed=true" in capsys.readouterr().out


# ── 008 build_trends checkpoint chain + carry-forward ───────────────────────

def _write_daily(data_dir: Path, filename: str, prices: dict) -> None:
    daily_dir = data_dir / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    (daily_dir / f"{filename}.json").write_text(
        json.dumps(prices, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")


def _write_checkpoint(data_dir: Path, filename: str, prices: dict) -> None:
    cp_dir = data_dir / "checkpoints"
    cp_dir.mkdir(parents=True, exist_ok=True)
    (cp_dir / f"{filename}.json").write_text(
        json.dumps(prices, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")


class TestBuildTrendsWithCheckpoints:
    """008 build_trends：checkpoint chain + carry-forward。"""

    def test_chain_checkpoint_carry_forward(self, tmp_path):
        """有 checkpoint：chain 所有 checkpoint + delta carry forward。"""
        # checkpoint C1: 全量 {a: 100, b: 200}
        _write_checkpoint(tmp_path, "20260801", {"a": 100, "b": 200})
        # daily C+1: a 改價
        _write_daily(tmp_path, "20260802", {"a": 110})
        # daily C+2: b 改價
        _write_daily(tmp_path, "20260803", {"b": 210})

        trends = version_data.build_trends(tmp_path)

        # a: [C1:100, C+1:110, C+2:110(carry)]
        assert trends["a"] == [["2026-08-01", 100], ["2026-08-02", 110], ["2026-08-03", 110]]
        # b: [C1:200, C+1:200(carry), C+2:210]
        assert trends["b"] == [["2026-08-01", 200], ["2026-08-02", 200], ["2026-08-03", 210]]

    def test_multiple_checkpoints_chain(self, tmp_path):
        """多個 checkpoint：各 checkpoint 全量重置 carrier。"""
        _write_checkpoint(tmp_path, "20260801", {"a": 100})
        _write_daily(tmp_path, "20260802", {"a": 110})
        _write_checkpoint(tmp_path, "20260803", {"a": 999})  # 全量重置
        _write_daily(tmp_path, "20260804", {"a": 1000})

        trends = version_data.build_trends(tmp_path)
        assert trends["a"] == [
            ["2026-08-01", 100],
            ["2026-08-02", 110],
            ["2026-08-03", 999],  # checkpoint 重置
            ["2026-08-04", 1000],
        ]

    def test_flat_day_carry_forward(self, tmp_path):
        """平價日（無 daily）→ carry forward 補齊每一天。"""
        _write_checkpoint(tmp_path, "20260801", {"a": 100})
        # 20260802, 20260803 無 daily（平價日）
        _write_daily(tmp_path, "20260804", {"a": 110})

        trends = version_data.build_trends(tmp_path)
        assert trends["a"] == [
            ["2026-08-01", 100],
            ["2026-08-02", 100],  # carry
            ["2026-08-03", 100],  # carry
            ["2026-08-04", 110],
        ]

    def test_legacy_full_replay_no_checkpoint(self, tmp_path):
        """無 checkpoint → legacy 全量回放（現行行為）。"""
        _write_daily(tmp_path, "20260801", {"a": 100, "b": 200})
        _write_daily(tmp_path, "20260802", {"a": 110, "b": 200})
        _write_daily(tmp_path, "20260803", {"a": 110, "b": 210})

        trends = version_data.build_trends(tmp_path)
        assert trends["a"] == [["2026-08-01", 100], ["2026-08-02", 110], ["2026-08-03", 110]]
        assert trends["b"] == [["2026-08-01", 200], ["2026-08-02", 200], ["2026-08-03", 210]]

    def test_corrupted_daily_skipped(self, tmp_path):
        """損壞的 daily 跳過不崩潰（carry forward 補齊）。"""
        _write_checkpoint(tmp_path, "20260801", {"a": 100})
        (tmp_path / "daily").mkdir()
        (tmp_path / "daily" / "20260802.json").write_text("bad json!!!")
        _write_daily(tmp_path, "20260803", {"a": 110})

        trends = version_data.build_trends(tmp_path)
        # 20260802 跳過（壞檔），20260801 carrier carry 到 20260802（補齊），20260803 更新
        assert trends["a"] == [
            ["2026-08-01", 100],
            ["2026-08-02", 100],  # carry forward（壞檔日）
            ["2026-08-03", 110],
        ]

    def test_missing_daily_self_heal(self, tmp_path):
        """遺失的 daily → carry forward 補齊（缺失 ≤7 天）。"""
        _write_checkpoint(tmp_path, "20260801", {"a": 100})
        # 20260802 遺失（無 daily 檔）
        _write_daily(tmp_path, "20260803", {"a": 110})

        trends = version_data.build_trends(tmp_path)
        assert trends["a"] == [
            ["2026-08-01", 100],
            ["2026-08-02", 100],  # carry forward（遺失日）
            ["2026-08-03", 110],
        ]

    def test_idempotent(self, tmp_path):
        """冪等：同輸入 → 同輸出。"""
        _write_checkpoint(tmp_path, "20260801", {"a": 100})
        _write_daily(tmp_path, "20260802", {"a": 110})

        t1 = version_data.build_trends(tmp_path)
        t2 = version_data.build_trends(tmp_path)
        assert t1 == t2

    def test_empty_trends_when_no_data(self, tmp_path):
        """無任何 daily/checkpoint → 空 dict。"""
        assert version_data.build_trends(tmp_path) == {}

    def test_pure_checkpoint_day_no_daily(self, tmp_path):
        """checkpoint 日無 daily（純 checkpoint）→ checkpoint 點出現。"""
        _write_checkpoint(tmp_path, "20260801", {"a": 100})
        _write_checkpoint(tmp_path, "20260808", {"a": 200})
        # 中間無 daily（平價）

        trends = version_data.build_trends(tmp_path)
        assert trends["a"] == [
            ["2026-08-01", 100],
            ["2026-08-02", 100],  # carry
            ["2026-08-03", 100],
            ["2026-08-04", 100],
            ["2026-08-05", 100],
            ["2026-08-06", 100],
            ["2026-08-07", 100],
            ["2026-08-08", 200],  # checkpoint 重置
        ]

    def test_legacy_and_checkpoint_coexist(self, tmp_path):
        """遷移相容：checkpoint 之前的 legacy daily 以 delta 語意回放。"""
        # 20260801, 20260802 為 legacy 全量 daily（無 checkpoint）
        _write_daily(tmp_path, "20260801", {"a": 100})
        _write_daily(tmp_path, "20260802", {"a": 110})
        # 20260805 為 checkpoint（之後為稀疏 delta）
        _write_checkpoint(tmp_path, "20260805", {"a": 200})
        _write_daily(tmp_path, "20260806", {"a": 210})

        trends = version_data.build_trends(tmp_path)
        # legacy daily 為 delta（carrier.update）、checkpoint 為全量重置
        # 20260803, 20260804 無事件 → carry forward
        assert trends["a"] == [
            ["2026-08-01", 100],  # delta
            ["2026-08-02", 110],  # delta
            ["2026-08-03", 110],  # carry forward
            ["2026-08-04", 110],  # carry forward
            ["2026-08-05", 200],  # checkpoint 重置
            ["2026-08-06", 210],  # delta
        ]

    def test_date_dedup(self, tmp_path):
        """同日去重。"""
        _write_checkpoint(tmp_path, "20260801", {"a": 100})
        _write_daily(tmp_path, "20260801", {"a": 110})  # 同日衝突

        trends = version_data.build_trends(tmp_path)
        # checkpoint 先執行（events 排序），delta 再更新 → 最終值 110
        # 但同日只留一點（dedupe）
        assert len(trends["a"]) == 1
        assert trends["a"][0] == ["2026-08-01", 110]