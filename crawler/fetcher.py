"""抓取 m-list.php 分類頁：httpx + CP950 解碼 + 重試退避。

職責：依序抓取 9 個分類頁；單頁失敗自動重試（≤ max_retries 次、指數退避 2^n 秒）；
Big5（CP950）解碼（errors='replace'，BDD #17 特殊字元不中斷）。
並發模型：無（依序抓取，對來源禮貌性）。HTTP 逾時上限 20 秒（Tech Decision 10–30s 區間）。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from .categories import CATEGORIES, Category

logger = logging.getLogger(__name__)

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
LIST_URL = "https://www.coolpc.com.tw/m/m-list.php"


class FetchError(Exception):
    """單一頁面在重試上限內仍失敗（由 fetch_all 捕捉並標記 html=None）。

    攜帶 g_index 與 url（007 警報與 meta.sources 所需）。
    """

    def __init__(self, g_index: int, url: str, msg: str):
        self.g_index = g_index
        self.url = url
        self.msg = msg
        super().__init__(f"[G={g_index}] {url}: {msg}")


@dataclass
class FetchResult:
    category: Category
    html: str | None  # CP950 解碼後文字；None = 該分類抓取失敗
    raw_bytes: bytes | None


class Fetcher:
    """依序抓取分類頁。重試上限 3 次（BDD #13），指數退避 backoff_sec * 2^n 秒。"""

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        max_retries: int = 3,
        backoff_sec: float = 2.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self._max_retries = max_retries
        self._backoff_sec = backoff_sec
        # transport 僅供測試注入（httpx.MockTransport），預設 None = 真實連線
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": MOBILE_UA},
            transport=transport,
        )

    def fetch_page(self, category: Category) -> bytes:
        """GET m-list.php?G=<g_index> → 回傳原始位元組。

        每次失敗依 retry 次數指數退避（backoff_sec * 2^n 秒）；
        超過 max_retries 拋 FetchError。
        """
        url = category.url
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.get(url)
                response.raise_for_status()
                return response.content
            except httpx.HTTPError as exc:
                if attempt >= self._max_retries:
                    raise FetchError(
                        category.g_index, url, f"{type(exc).__name__}: {exc}"
                    ) from exc
                delay = self._backoff_sec * (2**attempt)
                logger.warning(
                    "fetch failed %s (attempt %d/%d), retry in %.1fs: %s",
                    url, attempt + 1, self._max_retries + 1, delay, exc,
                )
                time.sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover

    def decode(self, raw: bytes) -> str:
        """CP950 解碼，errors='replace'（BDD #17：特殊字元以 U+FFFD 替代，不中斷）。"""
        return raw.decode("cp950", errors="replace")

    def fetch_all(self) -> list[FetchResult]:
        """依 CATEGORIES 順序逐頁抓取；單頁失敗 → html=None 記入結果，
        其餘分類照常抓取（BDD #12 單一分類頁失敗沿用舊資料並繼續）。"""
        results: list[FetchResult] = []
        for category in CATEGORIES:
            try:
                raw = self.fetch_page(category)
            except FetchError as exc:
                logger.error("category %s (G=%d) fetch failed: %s", category.name, category.g_index, exc)
                results.append(FetchResult(category, None, None))
            else:
                results.append(FetchResult(category, self.decode(raw), raw))
        return results
