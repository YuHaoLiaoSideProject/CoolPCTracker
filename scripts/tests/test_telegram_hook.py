"""telegram_hook.py 測試：實際 `sendMessage` 行為、graceful skip、錯誤容忍。

策略：起一個本機 HTTP stub（`http.server`）當 Telegram API，把 `TELEGRAM_API_BASE`
指向它，因此走的是**真實 httpx 請求**（含 URL 組法、JSON payload、截斷），
完全不打外網、也不需要假 token。

涵蓋（功能 002 §1.6 整合點 + 本次告警修復驗收）：
- 成功路徑：stub 回 200/ok → send_message True，endpoint/chat_id/text 正確
- 失敗路徑：HTTP 401/500、連線失敗 → False 且不拋例外
- 缺 env（token / chat_id）→ graceful skip（warning、不 crash）
- 4096 字元截斷
- CLI：讀 meta.json 發摘要（ok / partial / failed）、`--text`、`--dry-run`、
  `TELEGRAM_NOTIFY_SUCCESS=0` 關閉成功摘要、meta 缺檔時不中斷
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import telegram_hook

TOKEN = "123456789:TEST-BOT-TOKEN"
CHAT_ID = "-1001234567890"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """預設清空 Telegram 相關環境變數，避免測試互相污染或誤打外網。"""
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_API_BASE",
                "TELEGRAM_NOTIFY_SUCCESS"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def stub():
    """本機 Telegram API stub：記錄請求，可指定回應狀態與 body。"""
    state = {"requests": [], "status": 200, "body": {"ok": True, "result": {"message_id": 1}}}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 — http.server 介面
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode("utf-8")
            state["requests"].append({"path": self.path, "json": json.loads(raw or "{}")})
            payload = json.dumps(state["body"]).encode("utf-8")
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):  # 靜音 access log
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()


def _set_env(monkeypatch, base: str) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", CHAT_ID)
    monkeypatch.setenv("TELEGRAM_API_BASE", base)


# ── send_message：成功路徑 ───────────────────────────────────────────────────


class TestSendMessageSuccess:
    def test_posts_sendmessage_with_chat_id_and_text(self, monkeypatch, stub):
        base, state = stub
        _set_env(monkeypatch, base)

        assert telegram_hook.send_message("測試告警") is True

        assert len(state["requests"]) == 1
        request = state["requests"][0]
        assert request["path"] == f"/bot{TOKEN}/sendMessage"
        assert request["json"]["chat_id"] == CHAT_ID
        assert request["json"]["text"] == "測試告警"

    def test_explicit_credentials_override_env(self, monkeypatch, stub):
        """未設 env 時，顯式參數仍可發送（library 介面）。"""
        base, state = stub

        assert telegram_hook.send_message("hi", token=TOKEN, chat_id=CHAT_ID,
                                          api_base=base) is True
        assert state["requests"][0]["path"] == f"/bot{TOKEN}/sendMessage"

    def test_notify_returns_none_and_sends(self, monkeypatch, stub):
        """`notify()` 符合 NotifyFn = Callable[[str], None]。"""
        base, state = stub
        _set_env(monkeypatch, base)

        assert telegram_hook.notify("從 crawler 注入的警報") is None
        assert state["requests"][0]["json"]["text"] == "從 crawler 注入的警報"


# ── send_message：失敗路徑（絕不拋例外） ─────────────────────────────────────


class TestSendMessageFailure:
    def test_http_401_returns_false_without_raising(self, monkeypatch, stub, caplog):
        base, state = stub
        state["status"] = 401
        state["body"] = {"ok": False, "description": "Unauthorized"}
        _set_env(monkeypatch, base)

        with caplog.at_level("WARNING"):
            assert telegram_hook.send_message("x") is False

        assert "401" in caplog.text
        assert TOKEN not in caplog.text  # token 不得外洩到 log

    def test_http_500_returns_false(self, monkeypatch, stub):
        base, state = stub
        state["status"] = 500
        state["body"] = {"ok": False}
        _set_env(monkeypatch, base)

        assert telegram_hook.send_message("x") is False

    def test_connection_error_returns_false(self, monkeypatch, caplog):
        """連線失敗（埠未開）→ False + warning，不拋例外。"""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", CHAT_ID)
        monkeypatch.setenv("TELEGRAM_API_BASE", "http://127.0.0.1:1")

        with caplog.at_level("WARNING"):
            assert telegram_hook.send_message("x") is False
        assert "發送失敗" in caplog.text

    def test_ok_false_body_returns_false(self, monkeypatch, stub):
        base, state = stub
        state["body"] = {"ok": False, "description": "chat not found"}
        _set_env(monkeypatch, base)

        assert telegram_hook.send_message("x") is False


# ── 缺 env → graceful skip ──────────────────────────────────────────────────


class TestMissingEnv:
    def test_missing_token_skips_with_warning(self, monkeypatch, stub, caplog):
        base, state = stub
        monkeypatch.setenv("TELEGRAM_CHAT_ID", CHAT_ID)
        monkeypatch.setenv("TELEGRAM_API_BASE", base)

        with caplog.at_level("WARNING"):
            assert telegram_hook.send_message("x") is False

        assert "TELEGRAM_BOT_TOKEN" in caplog.text
        assert state["requests"] == []  # 完全沒有發請求

    def test_missing_chat_id_skips_with_warning(self, monkeypatch, stub, caplog):
        base, state = stub
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
        monkeypatch.setenv("TELEGRAM_API_BASE", base)

        with caplog.at_level("WARNING"):
            assert telegram_hook.send_message("x") is False

        assert "TELEGRAM_CHAT_ID" in caplog.text
        assert state["requests"] == []

    def test_notify_without_env_does_not_raise(self):
        assert telegram_hook.notify("沒有設定 env") is None


# ── 4096 字元上限 ───────────────────────────────────────────────────────────


class TestTruncation:
    def test_truncate_keeps_within_limit_and_marks(self):
        text = "字" * 5000
        result = telegram_hook.truncate(text)
        assert len(result) <= telegram_hook.TELEGRAM_MAX_LEN
        assert result.endswith("已截斷）")

    def test_short_text_unchanged(self):
        assert telegram_hook.truncate("短訊息") == "短訊息"

    def test_long_message_truncated_before_sending(self, monkeypatch, stub):
        base, state = stub
        _set_env(monkeypatch, base)

        assert telegram_hook.send_message("A" * 6000) is True
        sent_text = state["requests"][0]["json"]["text"]
        assert len(sent_text) <= 4096
        assert sent_text.endswith("已截斷）")


# ── CLI（工作流整合點） ─────────────────────────────────────────────────────


def _write_meta(data_dir: Path, **overrides) -> Path:
    meta = {
        "crawled_at": "2026-11-09T06:12:33.123456+00:00",
        "total": 1372,
        "previous_total": 1418,
        "changed": 12,
        "failed_categories": [],
        "status": "ok",
    }
    meta.update(overrides)
    path = data_dir / "meta.json"
    path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return path


class TestCli:
    def test_ok_meta_sends_success_summary(self, monkeypatch, stub, tmp_path):
        """成功路徑：status=ok → 仍發出摘要（每日心跳，可由 env 關閉）。"""
        base, state = stub
        _set_env(monkeypatch, base)
        _write_meta(tmp_path)

        assert telegram_hook.main(["--data-dir", str(tmp_path)]) == 0

        text = state["requests"][0]["json"]["text"]
        assert "執行成功" in text
        assert "2026-11-09" in text
        assert "1372" in text and "1418" in text

    def test_success_summary_can_be_disabled(self, monkeypatch, stub, tmp_path):
        base, state = stub
        _set_env(monkeypatch, base)
        monkeypatch.setenv("TELEGRAM_NOTIFY_SUCCESS", "0")
        _write_meta(tmp_path)

        assert telegram_hook.main(["--data-dir", str(tmp_path)]) == 0
        assert state["requests"] == []

    def test_failed_meta_sends_alert(self, monkeypatch, stub, tmp_path):
        base, state = stub
        _set_env(monkeypatch, base)
        _write_meta(tmp_path, status="failed", total=0, failed_categories=["CPU", "主機板"])

        assert telegram_hook.main(["--data-dir", str(tmp_path)]) == 0

        text = state["requests"][0]["json"]["text"]
        assert "執行失敗" in text
        assert "CPU、主機板" in text

    def test_partial_meta_sends_alert(self, monkeypatch, stub, tmp_path):
        base, state = stub
        _set_env(monkeypatch, base)
        _write_meta(tmp_path, status="partial", failed_categories=["主機板"])

        assert telegram_hook.main(["--data-dir", str(tmp_path)]) == 0
        assert "部分分類失敗" in state["requests"][0]["json"]["text"]

    def test_explicit_text_overrides_meta(self, monkeypatch, stub, tmp_path):
        base, state = stub
        _set_env(monkeypatch, base)
        _write_meta(tmp_path)

        assert telegram_hook.main(["--data-dir", str(tmp_path), "--text", "手動訊息"]) == 0
        assert state["requests"][0]["json"]["text"] == "手動訊息"

    def test_dry_run_prints_without_sending(self, monkeypatch, stub, tmp_path, capsys):
        base, state = stub
        _set_env(monkeypatch, base)
        _write_meta(tmp_path, status="failed")

        assert telegram_hook.main(["--data-dir", str(tmp_path), "--dry-run"]) == 0
        assert state["requests"] == []
        assert "執行失敗" in capsys.readouterr().out

    def test_missing_meta_file_returns_zero(self, monkeypatch, stub, tmp_path, caplog):
        base, state = stub
        _set_env(monkeypatch, base)

        with caplog.at_level("WARNING"):
            assert telegram_hook.main(["--data-dir", str(tmp_path / "nope")]) == 0
        assert state["requests"] == []
        assert "找不到" in caplog.text

    def test_broken_meta_json_returns_zero(self, monkeypatch, stub, tmp_path):
        base, state = stub
        _set_env(monkeypatch, base)
        (tmp_path / "meta.json").write_text("{not json", encoding="utf-8")

        assert telegram_hook.main(["--data-dir", str(tmp_path)]) == 0
        assert state["requests"] == []

    def test_missing_env_still_exits_zero(self, monkeypatch, stub, tmp_path):
        base, state = stub
        monkeypatch.setenv("TELEGRAM_API_BASE", base)
        _write_meta(tmp_path)

        assert telegram_hook.main(["--data-dir", str(tmp_path)]) == 0
        assert state["requests"] == []


# ── 訊息組裝 ────────────────────────────────────────────────────────────────


class TestFormatSummary:
    def test_ok_summary_contains_run_facts(self):
        meta = {"crawled_at": "2026-11-09T06:12:33+00:00", "total": 1372,
                "previous_total": 1418, "changed": 12, "status": "ok",
                "failed_categories": []}
        text = telegram_hook.format_summary(meta)
        assert "執行成功" in text
        assert "執行時間（UTC）：2026-11-09T06:12:33+00:00" in text
        assert "失敗分類：無" in text

    def test_failed_summary_lists_categories(self):
        meta = {"crawled_at": "2026-11-09T06:12:33+00:00", "total": 0,
                "previous_total": 1418, "changed": 0, "status": "failed",
                "failed_categories": ["CPU"]}
        text = telegram_hook.format_summary(meta)
        assert "執行失敗" in text
        assert "失敗分類：CPU" in text
