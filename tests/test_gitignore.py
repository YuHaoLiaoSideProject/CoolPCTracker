"""repo 基建測試：.gitignore 版控範圍（功能 002 §1.1 資料檔入庫）。

以 `git check-ignore -q`（subprocess）驗證：
- data/items.json、data/meta.json、data/items.v*.json、data/telegram.json 不再被忽略（入庫）
- data/secret.txt（其他 data/ 內容）仍被忽略
- web/node_modules/ 被忽略（前端依賴不入庫）

git check-ignore -q：exit 0 = 被忽略；exit 1 = 未被忽略。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

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


def test_versioned_data_files_not_ignored() -> None:
    """002 要版控的資料檔不再被 .gitignore 忽略（§1.1 data/ 入庫）。"""
    for path in [
        "data/items.json",          # 001 來源真相
        "data/meta.json",           # version/crawled_at/計數
        "data/items.v1.json",       # cache-busting 版本化快照（v1 起）
        "data/items.v10.json",      # 多位數版本（v9→v10 不誤傷）
        "data/telegram.json",       # 006 通知狀態（與 items.json 一併 commit）
    ]:
        assert not _git_check_ignore(path), f"{path} 應不再被 .gitignore 忽略"


def test_other_data_files_still_ignored() -> None:
    """非版控的 data/ 內容（爬蟲暫存等）仍被忽略。"""
    assert _git_check_ignore("data/secret.txt")
    assert _git_check_ignore("data/tmp/scratch.json")


def test_web_node_modules_ignored() -> None:
    """web/node_modules/ 應被忽略（前端依賴不入庫）。"""
    assert _git_check_ignore("web/node_modules/")
    assert _git_check_ignore("web/node_modules/vite/index.js")
