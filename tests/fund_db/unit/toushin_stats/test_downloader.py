"""Unit tests for fund_db.toushin_stats.downloader module.

Tests HTML scraping for link extraction and download flow using mock HTML.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from fund_db.exceptions import DownloadError
from fund_db.storage import FundDbStore
from fund_db.toushin_stats.downloader import ToushinStatsDownloader

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> FundDbStore:
    """Create a FundDbStore in a temporary directory."""
    return FundDbStore(data_dir=tmp_path / "fund_db")


@pytest.fixture
def mock_stats_html() -> str:
    """Create mock HTML simulating the IMAJ statistics page."""
    return """
    <html>
    <head><title>統計データ</title></head>
    <body>
    <h1>投資信託に関する統計等</h1>
    <div class="content">
        <h2>B ファンドの状況</h2>
        <ul>
            <li>
                <a href="/statistics/files/B1_shisan_zougen.xlsx">
                    B-1 資産増減状況（実額）
                </a>
            </li>
            <li>
                <a href="/statistics/files/B2_shohin_bunrui.xlsx">
                    B-2 商品分類別
                </a>
            </li>
            <li>
                <a href="/statistics/files/B3_unyo_kaisha.xlsx">
                    B-3 運用会社別
                </a>
            </li>
        </ul>
        <h2>A 全体像</h2>
        <ul>
            <li>
                <a href="/statistics/files/A2_zentaizou.xlsx">
                    A-2 全体像
                </a>
            </li>
        </ul>
        <h2>その他</h2>
        <ul>
            <li>
                <a href="/statistics/files/other_data.pdf">
                    PDFレポート
                </a>
            </li>
        </ul>
    </div>
    </body>
    </html>
    """


@pytest.fixture
def mock_stats_html_partial() -> str:
    """Create mock HTML with only B-1 and A-2 links."""
    return """
    <html>
    <body>
    <ul>
        <li><a href="/files/B1_shisan_zougen.xlsx">B-1 資産増減</a></li>
        <li><a href="/files/A2_zentaizou.xlsx">A-2 全体像</a></li>
    </ul>
    </body>
    </html>
    """


@pytest.fixture
def mock_stats_html_empty() -> str:
    """Create mock HTML with no xlsx links."""
    return """
    <html>
    <body>
    <p>No data available</p>
    </body>
    </html>
    """


# ---------------------------------------------------------------------------
# Tests: _extract_download_links
# ---------------------------------------------------------------------------


class TestExtractDownloadLinks:
    """Tests for ToushinStatsDownloader._extract_download_links()."""

    def test_正常系_全4リンクを正しく抽出できる(
        self,
        store: FundDbStore,
        mock_stats_html: str,
    ) -> None:
        downloader = ToushinStatsDownloader(store=store)
        links = downloader._extract_download_links(
            mock_stats_html,
            "https://www.toushin.or.jp/statistics/",
        )
        assert "b1" in links
        assert "b2" in links
        assert "b3" in links
        assert "a2" in links
        assert links["b1"].endswith("B1_shisan_zougen.xlsx")
        assert links["b2"].endswith("B2_shohin_bunrui.xlsx")
        assert links["b3"].endswith("B3_unyo_kaisha.xlsx")
        assert links["a2"].endswith("A2_zentaizou.xlsx")

    def test_正常系_部分的なリンクのみの場合も正しく抽出できる(
        self,
        store: FundDbStore,
        mock_stats_html_partial: str,
    ) -> None:
        downloader = ToushinStatsDownloader(store=store)
        links = downloader._extract_download_links(
            mock_stats_html_partial,
            "https://www.toushin.or.jp/",
        )
        assert "b1" in links
        assert "a2" in links
        assert "b2" not in links
        assert "b3" not in links

    def test_正常系_xlsxリンクなしで空辞書を返す(
        self,
        store: FundDbStore,
        mock_stats_html_empty: str,
    ) -> None:
        downloader = ToushinStatsDownloader(store=store)
        links = downloader._extract_download_links(
            mock_stats_html_empty,
            "https://www.toushin.or.jp/",
        )
        assert links == {}

    def test_正常系_相対URLが絶対URLに解決される(
        self,
        store: FundDbStore,
        mock_stats_html: str,
    ) -> None:
        downloader = ToushinStatsDownloader(store=store)
        links = downloader._extract_download_links(
            mock_stats_html,
            "https://www.toushin.or.jp/statistics/",
        )
        for url in links.values():
            assert url.startswith("https://")

    def test_正常系_PDFリンクは無視される(
        self,
        store: FundDbStore,
        mock_stats_html: str,
    ) -> None:
        downloader = ToushinStatsDownloader(store=store)
        links = downloader._extract_download_links(
            mock_stats_html,
            "https://www.toushin.or.jp/statistics/",
        )
        # Only 4 report links, no PDF
        assert len(links) == 4
        for url in links.values():
            assert not url.endswith(".pdf")


class TestExtractDownloadLinksEdgeCases:
    """Edge case tests for link extraction."""

    def test_エッジケース_大文字小文字混在のファイル名でも抽出できる(
        self,
        store: FundDbStore,
    ) -> None:
        html = """
        <html><body>
        <a href="/files/b1_Shisan_Zougen.xlsx">B-1 資産増減</a>
        </body></html>
        """
        downloader = ToushinStatsDownloader(store=store)
        links = downloader._extract_download_links(html, "https://www.toushin.or.jp/")
        assert "b1" in links

    def test_エッジケース_リンクテキストでパターンマッチする(
        self,
        store: FundDbStore,
    ) -> None:
        html = """
        <html><body>
        <a href="/files/data_001.xlsx">B-1 monthly data</a>
        </body></html>
        """
        downloader = ToushinStatsDownloader(store=store)
        links = downloader._extract_download_links(html, "https://www.toushin.or.jp/")
        assert "b1" in links


# ---------------------------------------------------------------------------
# Tests: Download error handling
# ---------------------------------------------------------------------------


class TestDownloadB1ErrorHandling:
    """Tests for download_b1 error handling."""

    def test_異常系_リンク未発見でDownloadError(
        self,
        store: FundDbStore,
    ) -> None:
        """When B-1 link is not found, download_b1 raises DownloadError."""
        downloader = ToushinStatsDownloader(store=store, timeout=0.5)

        # Monkey-patch _get_links to return empty dict
        downloader._get_links = lambda: {}  # type: ignore[method-assign]

        with pytest.raises(DownloadError):
            downloader.download_b1()

    def test_異常系_接続不可でDownloadError(
        self,
        store: FundDbStore,
    ) -> None:
        """When server is unreachable, _fetch_page raises DownloadError."""
        downloader = ToushinStatsDownloader(store=store, timeout=0.1)

        # Monkey-patch to use unreachable URL
        import fund_db.toushin_stats.downloader as dl_module

        original = dl_module.TOUSHIN_STATS_PAGE
        dl_module.TOUSHIN_STATS_PAGE = "http://127.0.0.1:1/nonexistent"
        try:
            with pytest.raises(DownloadError):
                downloader.download_b1()
        finally:
            dl_module.TOUSHIN_STATS_PAGE = original


# ---------------------------------------------------------------------------
# Tests: download_all behavior
# ---------------------------------------------------------------------------


class TestDownloadAll:
    """Tests for ToushinStatsDownloader.download_all()."""

    def test_正常系_リンクなしで空リストを返す(
        self,
        store: FundDbStore,
    ) -> None:
        downloader = ToushinStatsDownloader(store=store)
        # Monkey-patch _get_links to return empty dict
        downloader._get_links = lambda: {}  # type: ignore[method-assign]

        results = downloader.download_all()
        assert results == []


class TestFetchPage:
    """Tests for ToushinStatsDownloader._fetch_page()."""

    def test_異常系_不正URLでDownloadError(
        self,
        store: FundDbStore,
    ) -> None:
        downloader = ToushinStatsDownloader(store=store, timeout=0.1)
        with pytest.raises(DownloadError):
            downloader._fetch_page("http://127.0.0.1:1/nonexistent")
