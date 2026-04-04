"""Unit tests for fund_db.nisa.downloader module.

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
from fund_db.nisa.downloader import NisaDownloader
from fund_db.storage import FundDbStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> FundDbStore:
    """Create a FundDbStore in a temporary directory."""
    return FundDbStore(data_dir=tmp_path / "fund_db")


@pytest.fixture
def fake_xlsx_content() -> bytes:
    """Create minimal fake XLSX content for testing."""
    # Real XLSX files start with PK magic bytes (ZIP format)
    # Using a simple byte sequence for download testing
    return b"PK\x03\x04" + b"\x00" * 100


# ---------------------------------------------------------------------------
# Tests: NisaDownloader
# ---------------------------------------------------------------------------


class TestNisaDownloaderUnlisted:
    """Tests for NisaDownloader.download_unlisted()."""

    def test_正常系_非上場ファンドExcelをダウンロードできる(
        self,
        httpserver: HTTPServer,
        store: FundDbStore,
        fake_xlsx_content: bytes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        httpserver.expect_request(
            "/statistics/tsumitate/files/tsumitate_target.xlsx"
        ).respond_with_response(
            Response(
                response=fake_xlsx_content,
                status=200,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        )

        downloader = NisaDownloader(store=store)
        import fund_db.nisa.downloader as dl_module

        monkeypatch.setattr(
            dl_module,
            "NISA_UNLISTED_URL",
            httpserver.url_for("/statistics/tsumitate/files/tsumitate_target.xlsx"),
        )

        result = downloader.download_unlisted()

        assert result.path.exists()
        assert result.size_bytes == len(fake_xlsx_content)
        assert result.path.name == "tsumitate_target.xlsx"
        assert result.downloaded_at is not None

    def test_異常系_HTTP404でDownloadError(
        self,
        httpserver: HTTPServer,
        store: FundDbStore,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        httpserver.expect_request(
            "/statistics/tsumitate/files/tsumitate_target.xlsx"
        ).respond_with_response(Response(response=b"Not Found", status=404))

        downloader = NisaDownloader(store=store)
        import fund_db.nisa.downloader as dl_module

        monkeypatch.setattr(
            dl_module,
            "NISA_UNLISTED_URL",
            httpserver.url_for("/statistics/tsumitate/files/tsumitate_target.xlsx"),
        )

        with pytest.raises(DownloadError) as exc_info:
            downloader.download_unlisted()
        assert exc_info.value.status_code == 404

    def test_異常系_HTTP500でDownloadError(
        self,
        httpserver: HTTPServer,
        store: FundDbStore,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        httpserver.expect_request(
            "/statistics/tsumitate/files/tsumitate_target.xlsx"
        ).respond_with_response(Response(response=b"Internal Server Error", status=500))

        downloader = NisaDownloader(store=store)
        import fund_db.nisa.downloader as dl_module

        monkeypatch.setattr(
            dl_module,
            "NISA_UNLISTED_URL",
            httpserver.url_for("/statistics/tsumitate/files/tsumitate_target.xlsx"),
        )

        with pytest.raises(DownloadError) as exc_info:
            downloader.download_unlisted()
        assert exc_info.value.status_code == 500


class TestNisaDownloaderListed:
    """Tests for NisaDownloader.download_listed()."""

    def test_正常系_上場ETF_Excelをダウンロードできる(
        self,
        httpserver: HTTPServer,
        store: FundDbStore,
        fake_xlsx_content: bytes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        httpserver.expect_request(
            "/statistics/tsumitate/files/tsumitate_target_etf.xlsx"
        ).respond_with_response(
            Response(
                response=fake_xlsx_content,
                status=200,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        )

        downloader = NisaDownloader(store=store)
        import fund_db.nisa.downloader as dl_module

        monkeypatch.setattr(
            dl_module,
            "NISA_LISTED_URL",
            httpserver.url_for("/statistics/tsumitate/files/tsumitate_target_etf.xlsx"),
        )

        result = downloader.download_listed()

        assert result.path.exists()
        assert result.size_bytes == len(fake_xlsx_content)
        assert result.path.name == "tsumitate_target_etf.xlsx"
        assert result.downloaded_at is not None


class TestNisaDownloaderAll:
    """Tests for NisaDownloader.download_all()."""

    def test_正常系_両ファイルをダウンロードできる(
        self,
        httpserver: HTTPServer,
        store: FundDbStore,
        fake_xlsx_content: bytes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        httpserver.expect_request(
            "/statistics/tsumitate/files/tsumitate_target.xlsx"
        ).respond_with_response(
            Response(
                response=fake_xlsx_content,
                status=200,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        )
        httpserver.expect_request(
            "/statistics/tsumitate/files/tsumitate_target_etf.xlsx"
        ).respond_with_response(
            Response(
                response=fake_xlsx_content,
                status=200,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        )

        downloader = NisaDownloader(store=store)
        import fund_db.nisa.downloader as dl_module

        monkeypatch.setattr(
            dl_module,
            "NISA_UNLISTED_URL",
            httpserver.url_for("/statistics/tsumitate/files/tsumitate_target.xlsx"),
        )
        monkeypatch.setattr(
            dl_module,
            "NISA_LISTED_URL",
            httpserver.url_for("/statistics/tsumitate/files/tsumitate_target_etf.xlsx"),
        )

        results = downloader.download_all()

        assert len(results) == 2
        assert all(r.path.exists() for r in results)
        assert results[0].path.name == "tsumitate_target.xlsx"
        assert results[1].path.name == "tsumitate_target_etf.xlsx"


class TestNisaDownloaderSaveVerification:
    """Tests verifying that downloaded files are correctly saved via FundDbStore."""

    def test_正常系_保存先ディレクトリ構造が正しい(
        self,
        httpserver: HTTPServer,
        store: FundDbStore,
        fake_xlsx_content: bytes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        httpserver.expect_request(
            "/statistics/tsumitate/files/tsumitate_target.xlsx"
        ).respond_with_response(
            Response(
                response=fake_xlsx_content,
                status=200,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        )

        downloader = NisaDownloader(store=store)
        import fund_db.nisa.downloader as dl_module

        monkeypatch.setattr(
            dl_module,
            "NISA_UNLISTED_URL",
            httpserver.url_for("/statistics/tsumitate/files/tsumitate_target.xlsx"),
        )

        result = downloader.download_unlisted()

        # Verify directory structure: data_dir/nisa_unlisted/{date}/raw/tsumitate_target.xlsx
        assert "nisa_unlisted" in str(result.path)
        assert "raw" in str(result.path)
        assert result.path.read_bytes() == fake_xlsx_content

    def test_正常系_ダウンロード済みファイルの内容が一致する(
        self,
        httpserver: HTTPServer,
        store: FundDbStore,
        fake_xlsx_content: bytes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        httpserver.expect_request(
            "/statistics/tsumitate/files/tsumitate_target_etf.xlsx"
        ).respond_with_response(
            Response(
                response=fake_xlsx_content,
                status=200,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        )

        downloader = NisaDownloader(store=store)
        import fund_db.nisa.downloader as dl_module

        monkeypatch.setattr(
            dl_module,
            "NISA_LISTED_URL",
            httpserver.url_for("/statistics/tsumitate/files/tsumitate_target_etf.xlsx"),
        )

        result = downloader.download_listed()

        saved_content = result.path.read_bytes()
        assert saved_content == fake_xlsx_content
        assert len(saved_content) == result.size_bytes


class TestNisaDownloaderConnectionError:
    """Tests for connection errors (unreachable server)."""

    def test_異常系_接続不可でDownloadError(
        self,
        store: FundDbStore,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        downloader = NisaDownloader(store=store, timeout=0.1)
        import fund_db.nisa.downloader as dl_module

        monkeypatch.setattr(
            dl_module,
            "NISA_UNLISTED_URL",
            "http://127.0.0.1:1/nonexistent",
        )

        with pytest.raises(DownloadError):
            downloader.download_unlisted()
