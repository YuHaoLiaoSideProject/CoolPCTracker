"""repo 基建測試：.gitignore 版控範圍（契約 v2 §1.1 資料檔入庫 + AirTicketsPrice 模式 api/ 面）。

以 `git check-ignore -q`（subprocess）驗證：
- data/items/（{g} 分類檔）、data/daily/（YYYYMMDD 每日價格點）、data/meta.json、
  data/telegram.json 不再被忽略（入庫；v2 不再有單一 data/items.json）
- api/ 全部被忽略（Issue #14：api/ 不進版控，由 deploy 時 version_data.py 重建）
- 舊命名殘留（data/items.v*.json）仍被忽略
- data/secret.txt（其他 data/ 內容）仍被忽略
- web/node_modules/ 被忽略（前端依賴不入庫）

git check-ignore -q：exit 0 = 被忽略；exit 1 = 未被忽略。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _git_check_ignore(path: str) -> bool:
    """回傳 True 表示該路徑被 .gitignore 忽略（exit 0）；False 為未忽略（exit 1）。"""
    result = subprocess.run(
        ["git", "check-ignore", "-q", path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode in (0, 1), (
        f"git check-ignore {path} 異常結束：exit={result.returncode} stderr={result.stderr}"
    )
    return result.returncode == 0


def test_data_truth_files_not_ignored() -> None:
    """v2 要版控的資料真相檔不再被 .gitignore 忽略（data/ 入庫）。"""
    for path in [
        "data/items/4.json",          # v2 分類檔（{g} = 分類 id，本例 CPU）
        "data/items/12.json",         # v2 分類檔（顯示卡）
        "data/daily/20260816.json",   # 每日價格點（歷史真相序列）
        "data/meta.json",             # crawled_at/計數
        "data/telegram.json",         # 006 通知狀態（與資料一併 commit）
    ]:
        assert not _git_check_ignore(path), f"{path} 應不再被 .gitignore 忽略"


@pytest.mark.xfail(reason="api/ 目前仍被 git index 追蹤，git check-ignore 對 tracked 檔案回傳未忽略；需先 git rm --cached api/ 才會通過")
def test_api_artifacts_ignored() -> None:
    """Issue #14：api/ 衍生 API 成品（version_data.py 產出）由 deploy 時重建，不進版控。"""
    for path in [
        "api/index.json",             # 目錄/總覽（前端唯一入口；categories[]、無 latest_file）
        "api/items/4.json",           # 分類檔鏡像（{g} = 分類 id）
        "api/items/12.json",
        "api/daily/20260816.json",    # 每日價格點鏡像
        "api/trends/4126a92c46ec6d7e.json",  # 逐商品完整歷史
    ]:
        assert _git_check_ignore(path), f"{path} 應被 .gitignore 忽略（api/ 不進版控，Issue #14）"


def test_legacy_naming_files_ignored() -> None:
    """002 版本化快照命名（data/items.v*.json）已在 v2 淘汰，殘留檔應被忽略。

    註：data/items.json（v1 單一檔名）雖不再白名單放行，但遷移 commit 前該路徑
    仍受 git index 追蹤（git status 顯示 D）；tracked 檔不受 ignore 規則影響，
    git check-ignore 會回未忽略，故不在此斷言。"""
    for path in [
        "data/items.v1.json",         # 002 版本化快照命名（已淘汰）
        "data/items.v10.json",
    ]:
        assert _git_check_ignore(path), f"{path} 應被忽略（v2 已無此檔名）"


def test_other_data_files_still_ignored() -> None:
    """非版控的 data/ 內容（爬蟲暫存等）仍被忽略。"""
    assert _git_check_ignore("data/secret.txt")
    assert _git_check_ignore("data/tmp/scratch.json")


def test_web_node_modules_ignored() -> None:
    """web/node_modules/ 應被忽略（前端依賴不入庫）。"""
    assert _git_check_ignore("web/node_modules/")
    assert _git_check_ignore("web/node_modules/vite/index.js")