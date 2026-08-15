"""telegram_hook.py 單元測試（功能 002 §1.6 + BDD @integration @placeholder）。

涵蓋：無 TELEGRAM_BOT_TOKEN → notice 且回傳 0；有 token → placeholder 且回傳 0。
兩者皆不中斷 run（工作流配合 continue-on-error: true）。
"""
from __future__ import annotations

import telegram_hook


class TestTelegramHook:
    def test_no_token_returns_zero_and_prints_notice(self, monkeypatch, capsys):
        """無 TELEGRAM_BOT_TOKEN：印 notice（006 尚未啟用）並回傳 0。"""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

        assert telegram_hook.main() == 0

        out = capsys.readouterr().out
        assert "未設定 TELEGRAM_BOT_TOKEN" in out
        assert "006" in out

    def test_with_token_returns_zero_and_prints_placeholder(self, monkeypatch, capsys):
        """有 TELEGRAM_BOT_TOKEN：印 placeholder 訊息並回傳 0（006 未實作不中斷）。"""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:TEST-BOT-TOKEN")

        assert telegram_hook.main() == 0

        out = capsys.readouterr().out
        assert "placeholder" in out
        assert "006" in out
