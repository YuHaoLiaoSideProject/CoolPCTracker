"""fetcher.py 單元測試（BDD #7 僅抓 9 分類、#12 單頁失敗沿用舊資料並繼續、
#13 抓取失敗重試成功 / 連續失敗拋 FetchError / 指數退避、#17 CP950 特殊字元）。

Mock 策略：Fetcher 接受可注入的 transport（httpx.MockTransport），測試不建立
任何真實連線；重試次數與退避間隔以 handler 呼叫計數 + mock time.sleep 驗證；
URL 順序以 patch httpx.Client 的 Mock 驗證（Client.get 呼叫次數與引數）。
"""
from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from crawler.categories import CATEGORIES
from crawler.fetcher import Fetcher, FetchError, MOBILE_UA

OK_TEXT = "<html><body>原價屋手機版 CPU 價格</body></html>"
OK_BYTES = OK_TEXT.encode("big5")

G_INDEXES = (1, 3, 4, 5, 6, 7, 8, 9, 12)


def url_for(g_index: int) -> str:
    return f"https://www.coolpc.com.tw/m/m-list.php?G={g_index}"


def _ok_response(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=OK_BYTES)


def _always_fail_counter(calls: dict) -> Callable[[httpx.Request], httpx.Response]:
    """回傳 handler：每次呼叫計數並拋 ConnectError（模擬連線失敗）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("connection refused", request=request)

    return handler


# ── fetch_page 成功路徑 ─────────────────────────────────────────────────────

class TestFetchPage:
    @pytest.mark.parametrize(
        "category", [CATEGORIES[0], CATEGORIES[2], CATEGORIES[8]],
        ids=lambda c: f"G{c.g_index}",
    )
    def test_returns_bytes_and_uses_category_url(self, category):
        """GET url 依 Category 產生（https://www.coolpc.com.tw/m/m-list.php?G=<g_index>），回傳 bytes。"""
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return httpx.Response(200, content=OK_BYTES)

        fetcher = Fetcher(transport=httpx.MockTransport(handler), timeout=5)
        raw = fetcher.fetch_page(category)
        assert raw == OK_BYTES
        assert seen == [url_for(category.g_index)]

    def test_request_uses_mobile_ua(self):
        """請求 header 含手機版 UA（MOBILE_UA 內含 iPhone）。"""
        assert "iPhone" in MOBILE_UA
        seen_ua: list[str | None] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_ua.append(request.headers.get("user-agent"))
            return httpx.Response(200, content=b"ok")

        fetcher = Fetcher(transport=httpx.MockTransport(handler), timeout=5)
        fetcher.fetch_page(CATEGORIES[0])
        assert seen_ua == [MOBILE_UA]


# ── 重試與指數退避（BDD #13） ───────────────────────────────────────────────

class TestRetryBackoff:
    def test_first_fail_then_retry_success(self, mocker):
        """首次失敗 → 第 1 次重試成功 → fetch_page 回傳 bytes（BDD #13）。"""
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.ConnectError("connection refused", request=request)
            return httpx.Response(200, content=OK_BYTES)

        mocker.patch("crawler.fetcher.time.sleep")
        fetcher = Fetcher(
            transport=httpx.MockTransport(handler), max_retries=3, backoff_sec=1,
        )
        raw = fetcher.fetch_page(CATEGORIES[1])  # G=3
        assert raw == OK_BYTES
        assert calls["n"] == 2  # 1 次原始失敗 + 1 次重試成功

    def test_exceeds_max_retries_raises_fetcherror_with_attributes(self, mocker):
        """連續失敗超過 max_retries（預設 3）→ 拋 FetchError，帶 g_index 與 url（BDD #13）。"""
        calls = {"n": 0}
        mocker.patch("crawler.fetcher.time.sleep")
        fetcher = Fetcher(
            transport=httpx.MockTransport(_always_fail_counter(calls)),
            max_retries=3, backoff_sec=1,
        )
        category = CATEGORIES[2]  # G=4
        with pytest.raises(FetchError) as exc_info:
            fetcher.fetch_page(category)
        err = exc_info.value
        assert err.g_index == 4
        assert err.url == url_for(4)
        assert calls["n"] == 4  # 1 次原始 + 3 次重試，全失敗

    def test_exponential_backoff_sleep_intervals(self, mocker):
        """指數退避：第 n 次失敗後、第 n+1 次重試前 sleep(backoff_sec * 2^n)。"""
        calls = {"n": 0}
        sleep = mocker.patch("crawler.fetcher.time.sleep")
        fetcher = Fetcher(
            transport=httpx.MockTransport(_always_fail_counter(calls)),
            max_retries=3, backoff_sec=1,
        )
        with pytest.raises(FetchError):
            fetcher.fetch_page(CATEGORIES[0])
        assert sleep.call_args_list == [mocker.call(1), mocker.call(2), mocker.call(4)]

    def test_max_retries_param_honored(self, mocker):
        """max_retries 參數生效：1 次原始 + max_retries 次重試。"""
        calls = {"n": 0}
        mocker.patch("crawler.fetcher.time.sleep")
        fetcher = Fetcher(
            transport=httpx.MockTransport(_always_fail_counter(calls)),
            max_retries=1, backoff_sec=0.01,
        )
        with pytest.raises(FetchError):
            fetcher.fetch_page(CATEGORIES[0])
        assert calls["n"] == 2  # 1 次原始 + 1 次重試


# ── CP950 解碼（BDD #17） ───────────────────────────────────────────────────

class TestDecode:
    @pytest.fixture()
    def fetcher(self) -> Fetcher:
        return Fetcher(transport=httpx.MockTransport(_ok_response), timeout=5)

    def test_cp950_chinese_roundtrip(self, fetcher):
        """CP950 正常中文解碼（以 big5 編碼位元組驗證 roundtrip）。"""
        text = "原價屋手機版顯示卡價格：NT$ 9,990"
        assert fetcher.decode(text.encode("big5")) == text

    def test_invalid_big5_byte_replaced_with_ufffd(self, fetcher):
        """無效 Big5 位元組（b'\\xff'）→ errors='replace'，不中斷、以 U+FFFD 替代。"""
        assert fetcher.decode(b"abc\xffdef") == "abc\ufffddef"
        assert fetcher.decode(b"\xff") == "\ufffd"

    def test_ascii_page_decoded_unchanged(self, fetcher):
        """純 ASCII 頁面解碼結果不變。"""
        assert fetcher.decode(b"<html>plain ascii</html>") == "<html>plain ascii</html>"


# ── fetch_all（BDD #7、#12） ────────────────────────────────────────────────

class TestFetchAll:
    def test_constructor_accepts_timeout_max_retries_backoff(self, mocker):
        """Fetcher 接受 timeout / max_retries / backoff_sec 參數（透傳給 httpx.Client）。"""
        mock_client = mocker.Mock()
        client_cls = mocker.patch("crawler.fetcher.httpx.Client", return_value=mock_client)
        Fetcher(timeout=12.5, max_retries=2, backoff_sec=3)
        _, kwargs = client_cls.call_args
        assert kwargs["timeout"] == 12.5
        assert kwargs["headers"]["User-Agent"] == MOBILE_UA

    def test_all_success_returns_nine_results_in_category_order(self):
        """全部成功 → 9 筆 FetchResult，依 CATEGORIES 順序，html/raw_bytes 齊全。"""
        fetcher = Fetcher(transport=httpx.MockTransport(_ok_response), timeout=5)
        results = fetcher.fetch_all()
        assert [r.category.g_index for r in results] == list(G_INDEXES)
        assert all(r.html == OK_TEXT for r in results)
        assert all(r.raw_bytes == OK_BYTES for r in results)

    def test_single_page_failure_marks_that_result_none_and_continues(self, mocker):
        """單一分類頁失敗（G=5）→ 該筆 html=None、其餘照常（BDD #12）。"""
        def handler(request: httpx.Request) -> httpx.Response:
            if "G=5" in str(request.url):
                raise httpx.ConnectError("timeout", request=request)
            return httpx.Response(200, content=OK_BYTES)

        mocker.patch("crawler.fetcher.time.sleep")
        fetcher = Fetcher(
            transport=httpx.MockTransport(handler), max_retries=3, backoff_sec=0.01,
        )
        results = fetcher.fetch_all()
        assert [r.category.g_index for r in results] == list(G_INDEXES)  # 順序不亂
        failed = next(r for r in results if r.category.g_index == 5)
        assert failed.html is None
        assert failed.raw_bytes is None
        for r in results:
            if r.category.g_index != 5:
                assert r.html == OK_TEXT
                assert r.raw_bytes == OK_BYTES

    def test_client_get_called_nine_times_with_url_order(self, mocker):
        """依序抓取：Client.get 被呼叫 9 次，URL 順序 G=1,3,4,5,6,7,8,9,12（BDD #7 延伸）。"""
        mock_client = mocker.Mock()
        mock_client.get.side_effect = [mocker.Mock(content=OK_BYTES) for _ in CATEGORIES]
        mocker.patch("crawler.fetcher.httpx.Client", return_value=mock_client)
        fetcher = Fetcher(timeout=5, max_retries=3, backoff_sec=1)
        results = fetcher.fetch_all()
        assert len(results) == 9
        assert mock_client.get.call_count == 9
        urls = [call.args[0] for call in mock_client.get.call_args_list]
        assert urls == [url_for(g) for g in G_INDEXES]
