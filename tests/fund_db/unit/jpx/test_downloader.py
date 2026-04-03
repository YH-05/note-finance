"""Unit tests for fund_db.jpx.downloader module.

Uses pytest-httpserver to mock HTTP endpoints and validate download flow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from werkzeug.wrappers import Response

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpserver import HTTPServer

from fund_db.exceptions import DownloadError
from fund_db.jpx.downloader import JpxDownloader
from fund_db.storage import FundDbStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> FundDbStore:
    """Create a FundDbStore in a temporary directory."""
    return FundDbStore(data_dir=tmp_path / "fund_db")


@pytest.fixture
def fake_xls_content() -> bytes:
    """Create minimal fake XLS content for testing.

    XLS files (OLE2 format) start with the magic bytes D0 CF 11 E0.
    """
    return b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100


# ---------------------------------------------------------------------------
# Tests: JpxDownloader.download()
# ---------------------------------------------------------------------------


class TestJpxDownloaderDownload:
    """Tests for JpxDownloader.download()."""

    def test_正常系_JPX_XLSファイルをダウンロードできる(
        self,
        httpserver: HTTPServer,
        store: FundDbStore,
        fake_xls_content: bytes,
    ) -> None:
        httpserver.expect_request(
            "/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
        ).respond_with_response(
            Response(
                response=fake_xls_content,
                status=200,
                content_type="application/vnd.ms-excel",
            )
        )

        downloader = JpxDownloader(store=store)
        import fund_db.jpx.downloader as dl_module

        original_url = dl_module.JPX_LISTED_URL
        dl_module.JPX_LISTED_URL = httpserver.url_for(
            "/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
        )
        try:
            result = downloader.download()
        finally:
            dl_module.JPX_LISTED_URL = original_url

        assert result.path.exists()
        assert result.size_bytes == len(fake_xls_content)
        assert result.path.name == "data_j.xls"
        assert result.downloaded_at is not None

    def test_異常系_HTTP404でDownloadError(
        self,
        httpserver: HTTPServer,
        store: FundDbStore,
    ) -> None:
        httpserver.expect_request(
            "/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
        ).respond_with_response(Response(response=b"Not Found", status=404))

        downloader = JpxDownloader(store=store)
        import fund_db.jpx.downloader as dl_module

        original_url = dl_module.JPX_LISTED_URL
        dl_module.JPX_LISTED_URL = httpserver.url_for(
            "/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
        )
        try:
            with pytest.raises(DownloadError) as exc_info:
                downloader.download()
            assert exc_info.value.status_code == 404
        finally:
            dl_module.JPX_LISTED_URL = original_url

    def test_異常系_HTTP500でDownloadError(
        self,
        httpserver: HTTPServer,
        store: FundDbStore,
    ) -> None:
        httpserver.expect_request(
            "/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
        ).respond_with_response(Response(response=b"Internal Server Error", status=500))

        downloader = JpxDownloader(store=store)
        import fund_db.jpx.downloader as dl_module

        original_url = dl_module.JPX_LISTED_URL
        dl_module.JPX_LISTED_URL = httpserver.url_for(
            "/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
        )
        try:
            with pytest.raises(DownloadError) as exc_info:
                downloader.download()
            assert exc_info.value.status_code == 500
        finally:
            dl_module.JPX_LISTED_URL = original_url


class TestJpxDownloaderSaveVerification:
    """Tests verifying that downloaded files are correctly saved via FundDbStore."""

    def test_正常系_保存先ディレクトリ構造が正しい(
        self,
        httpserver: HTTPServer,
        store: FundDbStore,
        fake_xls_content: bytes,
    ) -> None:
        httpserver.expect_request(
            "/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
        ).respond_with_response(
            Response(
                response=fake_xls_content,
                status=200,
                content_type="application/vnd.ms-excel",
            )
        )

        downloader = JpxDownloader(store=store)
        import fund_db.jpx.downloader as dl_module

        original_url = dl_module.JPX_LISTED_URL
        dl_module.JPX_LISTED_URL = httpserver.url_for(
            "/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
        )
        try:
            result = downloader.download()
        finally:
            dl_module.JPX_LISTED_URL = original_url

        # Verify directory structure: data_dir/jpx_listed/{date}/raw/data_j.xls
        assert "jpx_listed" in str(result.path)
        assert "raw" in str(result.path)
        assert result.path.read_bytes() == fake_xls_content

    def test_正常系_ダウンロード済みファイルの内容が一致する(
        self,
        httpserver: HTTPServer,
        store: FundDbStore,
        fake_xls_content: bytes,
    ) -> None:
        httpserver.expect_request(
            "/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
        ).respond_with_response(
            Response(
                response=fake_xls_content,
                status=200,
                content_type="application/vnd.ms-excel",
            )
        )

        downloader = JpxDownloader(store=store)
        import fund_db.jpx.downloader as dl_module

        original_url = dl_module.JPX_LISTED_URL
        dl_module.JPX_LISTED_URL = httpserver.url_for(
            "/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
        )
        try:
            result = downloader.download()
        finally:
            dl_module.JPX_LISTED_URL = original_url

        saved_content = result.path.read_bytes()
        assert saved_content == fake_xls_content
        assert len(saved_content) == result.size_bytes


class TestJpxDownloaderConnectionError:
    """Tests for connection errors (unreachable server)."""

    def test_異常系_接続不可でDownloadError(
        self,
        store: FundDbStore,
    ) -> None:
        downloader = JpxDownloader(store=store, timeout=0.1)
        import fund_db.jpx.downloader as dl_module

        original_url = dl_module.JPX_LISTED_URL
        dl_module.JPX_LISTED_URL = "http://127.0.0.1:1/nonexistent"
        try:
            with pytest.raises(DownloadError):
                downloader.download()
        finally:
            dl_module.JPX_LISTED_URL = original_url
