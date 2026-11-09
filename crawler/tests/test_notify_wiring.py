"""notify（告警）注入與錯誤隔離測試（本次「排程失敗無告警」修復驗收）。

驗證四件事：
1. 失敗路徑（健康檢查 failed）→ 注入的 notify 被呼叫，訊息含執行時間／失敗階段／原因
2. 例外路徑（run 拋錯、--date 無效）→ notify 被呼叫且 exit code 仍為 2
3. 缺 env → graceful skip（不 crash、不發請求）
4. notify 本身拋錯 → 不掩蓋原錯誤、不改變 exit code、不中斷 meta 落盤
以及 `main()` 確實把 hook 注入 `run_crawler`。

不使用真實網路：Fetcher 一律替換為 fake，notify 一律為測試記錄器。
"""
from __future__ import annotations

import logging

import pytest

import crawler.main as main_module
from crawler.categories import CATEGORIES
from crawler.fetcher import FetchResult
from crawler.main import main, run_crawler

DAY = "2026-11-09"


@pytest.fixture(autouse=True)
def clean_telegram_env(monkeypatch):
    """避免測試讀到真實憑證（缺 env 才是預設情境）。"""
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_API_BASE",
                "TELEGRAM_NOTIFY_SUCCESS"):
        monkeypatch.delenv(key, raising=False)


class _AllFetchFailedFetcher:
    """9 分類全部抓取失敗 → total=0 → 健康檢查 failed。"""

    def __init__(self, *args, **kwargs):
        pass

    def fetch_all(self) -> list[FetchResult]:
        return [FetchResult(category=c, html=None, raw_bytes=None) for c in CATEGORIES]


@pytest.fixture
def fetch_all_failed(monkeypatch):
    monkeypatch.setattr(main_module, "Fetcher", _AllFetchFailedFetcher)


@pytest.fixture
def recorder():
    sent: list[str] = []

    def _notify(text: str) -> None:
        sent.append(text)

    _notify.sent = sent  # type: ignore[attr-defined]
    return _notify


# ── 失敗路徑 ────────────────────────────────────────────────────────────────


class TestFailurePath:
    def test_failed_health_check_calls_notify_with_required_fields(
            self, tmp_path, fetch_all_failed, recorder):
        rc = run_crawler(tmp_path, today=None, notify=recorder)

        assert rc == 1
        assert len(recorder.sent) == 1
        text = recorder.sent[0]
        assert "階段：健康檢查" in text
        assert "執行時間（UTC）：" in text
        assert "0 商品" in text

    def test_failure_alert_includes_day_and_counts(self):
        from datetime import date

        from crawler.main import _build_alert

        text = _build_alert(date(2026, 11, 9), total=0, previous_total=1418,
                            failed_categories=["CPU", "主機板"], reason="本次解析出 0 商品")
        assert "2026-11-09" in text
        assert "階段：健康檢查" in text
        assert "失敗原因：本次解析出 0 商品" in text
        assert "失敗分類：CPU、主機板" in text
        assert "1418" in text

    def test_main_injects_notifier_into_run_crawler(self, monkeypatch):
        """main() 必須把載入的 notifier 傳給 run_crawler（原本的 bug 點）。"""
        sentinel = lambda text: None  # noqa: E731
        seen: dict[str, object] = {}

        monkeypatch.setattr(main_module, "_load_notifier", lambda: sentinel)

        def fake_run(data_dir, today=None, notify=None):
            seen["notify"] = notify
            return 0

        monkeypatch.setattr(main_module, "run_crawler", fake_run)

        assert main(["--data-dir", "/tmp/unused", "--date", DAY]) == 0
        assert seen["notify"] is sentinel

    def test_main_notifies_on_failed_run(self, tmp_path, monkeypatch, fetch_all_failed, recorder):
        monkeypatch.setattr(main_module, "_load_notifier", lambda: recorder)

        assert main(["--data-dir", str(tmp_path), "--date", DAY]) == 1
        assert len(recorder.sent) == 1
        assert "階段：健康檢查" in recorder.sent[0]


# ── 例外路徑（exit 2） ──────────────────────────────────────────────────────


class TestExceptionPath:
    def test_run_exception_notifies_and_returns_2(self, tmp_path, monkeypatch, recorder,
                                                  caplog):
        class _ExplodingFetcher:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("boom-fetch-init")

        monkeypatch.setattr(main_module, "Fetcher", _ExplodingFetcher)
        monkeypatch.setattr(main_module, "_load_notifier", lambda: recorder)

        with caplog.at_level(logging.ERROR, logger="crawler.main"):
            rc = main(["--data-dir", str(tmp_path), "--date", DAY])

        assert rc == 2
        assert len(recorder.sent) == 1
        text = recorder.sent[0]
        assert "階段：run_crawler（執行期例外）" in text
        assert "錯誤類型：RuntimeError" in text
        assert "boom-fetch-init" in text
        assert "執行時間（UTC）：" in text

    def test_invalid_date_notifies_and_returns_2(self, tmp_path, monkeypatch, recorder):
        monkeypatch.setattr(main_module, "_load_notifier", lambda: recorder)

        assert main(["--data-dir", str(tmp_path), "--date", "not-a-date"]) == 2
        assert len(recorder.sent) == 1
        assert "階段：CLI 參數解析（--date）" in recorder.sent[0]
        assert "錯誤類型：ValueError" in recorder.sent[0]

    def test_long_error_message_is_truncated(self):
        from crawler.main import _build_exception_alert

        exc = RuntimeError("x" * 5000)
        text = _build_exception_alert(None, "run_crawler（執行期例外）", exc)
        assert len(text) < 2000  # 已截斷，遠低於 Telegram 4096 上限
        assert "…" in text


# ── notify 自身失敗：不得掩蓋原錯誤 ─────────────────────────────────────────


class TestNotifyFailureIsolation:
    def test_notify_error_does_not_block_failed_meta(self, tmp_path, fetch_all_failed):
        """run_crawler 的失敗路徑：notify 拋錯仍要寫 meta.status=failed、回 1。"""
        def exploding_notify(text: str) -> None:
            raise RuntimeError("telegram-down")

        rc = run_crawler(tmp_path, today=None, notify=exploding_notify)

        assert rc == 1
        meta = (tmp_path / "meta.json").read_text(encoding="utf-8")
        assert '"status":"failed"' in meta

    def test_notify_error_does_not_mask_original_exception(self, tmp_path, monkeypatch,
                                                           caplog):
        """run_crawler 拋錯 + notify 也拋錯 → 原錯誤仍是被記錄的例外，rc=2。"""
        def exploding_notify(text: str) -> None:
            raise RuntimeError("notify-down")

        class _ExplodingFetcher:
            def __init__(self, *args, **kwargs):
                raise ValueError("boom-original")

        monkeypatch.setattr(main_module, "Fetcher", _ExplodingFetcher)
        monkeypatch.setattr(main_module, "_load_notifier", lambda: exploding_notify)

        with caplog.at_level(logging.WARNING, logger="crawler.main"):
            rc = main(["--data-dir", str(tmp_path), "--date", DAY])

        assert rc == 2  # 未被通知例外改成 crash / 其他 exit code
        logged = [str(r.exc_info[1]) for r in caplog.records if r.exc_info]
        assert any("boom-original" in msg for msg in logged)  # 原錯誤仍在 log
        assert any("notify-down" in msg for msg in logged)    # 通知錯誤另記，不覆蓋原錯誤

    def test_missing_env_notify_is_graceful(self, tmp_path, fetch_all_failed, caplog):
        """缺 env：真實 hook 被載入但只 warning，不 crash、不影響 exit code。"""
        notify = main_module._load_notifier()
        assert callable(notify)

        with caplog.at_level(logging.WARNING):
            rc = run_crawler(tmp_path, today=None, notify=notify)

        assert rc == 1
        assert "TELEGRAM_BOT_TOKEN" in caplog.text
        assert (tmp_path / "meta.json").exists()


# ── hook 載入容錯 ───────────────────────────────────────────────────────────


class TestLoadNotifier:
    def test_returns_callable(self):
        notify = main_module._load_notifier()
        assert callable(notify)
        assert notify("x") is None  # 無 env → skip，不拋例外

    def test_missing_hook_file_returns_none(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(main_module, "__file__", str(tmp_path / "nowhere" / "main.py"))

        with caplog.at_level(logging.WARNING, logger="crawler.main"):
            assert main_module._load_notifier() is None
        assert "找不到 telegram notify hook" in caplog.text

    def test_broken_hook_file_returns_none(self, tmp_path, monkeypatch, caplog):
        """hook 檔案語法錯誤 → 回 None + warning，爬蟲照常執行。"""
        repo = tmp_path / "repo"
        (repo / "crawler").mkdir(parents=True)
        (repo / "scripts").mkdir()
        (repo / "scripts" / "telegram_hook.py").write_text("def notify(:\n", encoding="utf-8")
        monkeypatch.setattr(main_module, "__file__", str(repo / "crawler" / "main.py"))

        with caplog.at_level(logging.WARNING, logger="crawler.main"):
            assert main_module._load_notifier() is None
        assert "載入 telegram notify hook 失敗" in caplog.text
