"""Tests for PDF downloader service and PDF store.

Tests cover:
- is_pdf_url() standalone function
- find_pdf_links() standalone function
- PdfDownloader.download() with mocked httpx
- PdfDownloader._derive_filename()
- PdfStore directory management and operations
- PdfStore.download_and_store() integration
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from report_scraper.exceptions import FetchError
from report_scraper.services.pdf_downloader import (
    PdfDownloader,
    _is_private_ip,
    find_pdf_links,
    is_pdf_url,
)
from report_scraper.storage.pdf_store import PdfStore
from report_scraper.types import PdfMetadata

# ---------------------------------------------------------------------------
# is_pdf_url tests
# ---------------------------------------------------------------------------


class TestIsPdfUrl:
    """Tests for is_pdf_url() standalone function."""

    def test_正常系_pdf拡張子のURLをTrueと判定(self) -> None:
        assert is_pdf_url("https://example.com/report.pdf") is True

    def test_正常系_大文字PDF拡張子もTrueと判定(self) -> None:
        assert is_pdf_url("https://example.com/report.PDF") is True

    def test_正常系_混合ケースもTrueと判定(self) -> None:
        assert is_pdf_url("https://example.com/report.Pdf") is True

    def test_正常系_クエリパラメータ付きもTrueと判定(self) -> None:
        assert is_pdf_url("https://example.com/report.pdf?token=abc") is True

    def test_正常系_htmlのURLをFalseと判定(self) -> None:
        assert is_pdf_url("https://example.com/page.html") is False

    def test_正常系_拡張子なしURLをFalseと判定(self) -> None:
        assert is_pdf_url("https://example.com/page") is False

    def test_エッジケース_空文字でFalse(self) -> None:
        assert is_pdf_url("") is False

    def test_正常系_パス深いURLでもTrueと判定(self) -> None:
        assert is_pdf_url("https://example.com/a/b/c/report.pdf") is True


# ---------------------------------------------------------------------------
# find_pdf_links tests
# ---------------------------------------------------------------------------


class TestFindPdfLinks:
    """Tests for find_pdf_links() standalone function."""

    def test_正常系_PDFリンクのみ抽出できる(self) -> None:
        el_pdf = MagicMock()
        el_pdf.attrib = {"href": "/docs/report.pdf"}
        el_html = MagicMock()
        el_html.attrib = {"href": "/docs/page.html"}

        result = find_pdf_links([el_pdf, el_html], "https://example.com")
        assert result == ["https://example.com/docs/report.pdf"]

    def test_正常系_絶対URLもそのまま処理(self) -> None:
        el = MagicMock()
        el.attrib = {"href": "https://cdn.example.com/report.pdf"}

        result = find_pdf_links([el], "https://example.com")
        assert result == ["https://cdn.example.com/report.pdf"]

    def test_正常系_重複URLは除外される(self) -> None:
        el1 = MagicMock()
        el1.attrib = {"href": "/report.pdf"}
        el2 = MagicMock()
        el2.attrib = {"href": "/report.pdf"}

        result = find_pdf_links([el1, el2], "https://example.com")
        assert len(result) == 1

    def test_正常系_href空のエレメントはスキップ(self) -> None:
        el = MagicMock()
        el.attrib = {"href": ""}

        result = find_pdf_links([el], "https://example.com")
        assert result == []

    def test_エッジケース_空リストで空結果(self) -> None:
        assert find_pdf_links([], "https://example.com") == []


# ---------------------------------------------------------------------------
# PdfDownloader._derive_filename tests
# ---------------------------------------------------------------------------


class TestDeriveFilename:
    """Tests for PdfDownloader._derive_filename."""

    def test_正常系_URLパスからファイル名を取得(self) -> None:
        result = PdfDownloader._derive_filename(
            "https://example.com/reports/q4-2025.pdf"
        )
        assert result == "q4-2025.pdf"

    def test_正常系_拡張子なしURLにはpdfを付与(self) -> None:
        result = PdfDownloader._derive_filename("https://example.com/download?id=123")
        assert result == "download.pdf"

    def test_正常系_パスが深いURLからも取得(self) -> None:
        result = PdfDownloader._derive_filename("https://example.com/a/b/c/report.pdf")
        assert result == "report.pdf"

    def test_エッジケース_クエリのみのURLでフォールバック(self) -> None:
        result = PdfDownloader._derive_filename("https://example.com/")
        assert result == "download.pdf"


# ---------------------------------------------------------------------------
# PdfDownloader.download tests
# ---------------------------------------------------------------------------


def _make_mock_client(
    *,
    status_code: int = 200,
    content: bytes = b"",
) -> MagicMock:
    """Create a mock httpx.AsyncClient with streaming support."""
    response = MagicMock()
    response.status_code = status_code

    async def _aiter_bytes(chunk_size: int = 65536) -> Any:
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]

    response.aiter_bytes = _aiter_bytes

    # stream() returns a sync context manager (not async in terms of __aenter__
    # being a coroutine). httpx.AsyncClient.stream returns an async CM.
    stream_cm = MagicMock()
    stream_cm.__aenter__ = AsyncMock(return_value=response)
    stream_cm.__aexit__ = AsyncMock(return_value=False)

    client = MagicMock()
    client.stream.return_value = stream_cm
    client.is_closed = False
    return client


class TestPdfDownloaderDownload:
    """Tests for PdfDownloader.download."""

    @pytest.mark.asyncio
    async def test_正常系_PDFをダウンロードして保存できる(self, tmp_path: Path) -> None:
        pdf_content = b"%PDF-1.4 fake pdf content" * 100
        mock_client = _make_mock_client(status_code=200, content=pdf_content)

        downloader = PdfDownloader()
        downloader._client = mock_client

        result = await downloader.download(
            "https://example.com/report.pdf",
            tmp_path,
        )

        assert isinstance(result, PdfMetadata)
        assert result.url == "https://example.com/report.pdf"
        assert result.size_bytes == len(pdf_content)
        assert result.local_path.exists()
        assert result.local_path.read_bytes() == pdf_content

    @pytest.mark.asyncio
    async def test_正常系_カスタムファイル名で保存できる(self, tmp_path: Path) -> None:
        pdf_content = b"%PDF-1.4 content"
        mock_client = _make_mock_client(status_code=200, content=pdf_content)

        downloader = PdfDownloader()
        downloader._client = mock_client

        result = await downloader.download(
            "https://example.com/download?id=123",
            tmp_path,
            filename="custom-report.pdf",
        )

        assert result.local_path.name == "custom-report.pdf"

    @pytest.mark.asyncio
    async def test_異常系_非200ステータスでFetchError(self, tmp_path: Path) -> None:
        mock_client = _make_mock_client(status_code=404, content=b"")

        downloader = PdfDownloader()
        downloader._client = mock_client

        with pytest.raises(FetchError, match="HTTP 404"):
            await downloader.download(
                "https://example.com/missing.pdf",
                tmp_path,
            )

    @pytest.mark.asyncio
    async def test_異常系_サイズ超過でFetchError(self, tmp_path: Path) -> None:
        large_content = b"x" * 1000
        mock_client = _make_mock_client(status_code=200, content=large_content)

        downloader = PdfDownloader(max_size=500)
        downloader._client = mock_client

        with pytest.raises(FetchError, match="exceeds maximum size"):
            await downloader.download(
                "https://example.com/huge.pdf",
                tmp_path,
            )

    @pytest.mark.asyncio
    async def test_異常系_タイムアウトでFetchError(self, tmp_path: Path) -> None:
        import httpx

        mock_client = MagicMock()
        mock_client.stream.side_effect = httpx.TimeoutException("timeout")
        mock_client.is_closed = False

        downloader = PdfDownloader()
        downloader._client = mock_client

        with pytest.raises(FetchError, match="timed out"):
            await downloader.download(
                "https://example.com/slow.pdf",
                tmp_path,
            )

    @pytest.mark.asyncio
    async def test_異常系_プライベートIPでFetchError(self, tmp_path: Path) -> None:
        downloader = PdfDownloader()
        with pytest.raises(FetchError, match="private/internal address"):
            await downloader.download(
                "https://127.0.0.1/report.pdf",
                tmp_path,
            )

    @pytest.mark.asyncio
    async def test_異常系_不正スキームでFetchError(self, tmp_path: Path) -> None:
        downloader = PdfDownloader()
        with pytest.raises(FetchError, match="Unsupported URL scheme"):
            await downloader.download(
                "ftp://example.com/report.pdf",
                tmp_path,
            )


# ---------------------------------------------------------------------------
# _is_private_ip tests
# ---------------------------------------------------------------------------


class TestIsPrivateIp:
    """Tests for _is_private_ip utility function."""

    def test_正常系_ループバックIPを検出(self) -> None:
        assert _is_private_ip("127.0.0.1") is True

    def test_正常系_プライベートIPを検出_10系(self) -> None:
        assert _is_private_ip("10.0.0.1") is True

    def test_正常系_プライベートIPを検出_172系(self) -> None:
        assert _is_private_ip("172.16.0.1") is True

    def test_正常系_プライベートIPを検出_192系(self) -> None:
        assert _is_private_ip("192.168.1.1") is True

    def test_正常系_パブリックIPでFalse(self) -> None:
        assert _is_private_ip("8.8.8.8") is False

    def test_正常系_空文字でFalse(self) -> None:
        assert _is_private_ip("") is False


# ---------------------------------------------------------------------------
# PdfStore tests
# ---------------------------------------------------------------------------


class TestPdfStore:
    """Tests for PdfStore storage manager."""

    def test_正常系_初期化でディレクトリを作成する(self, tmp_path: Path) -> None:
        store_dir = tmp_path / "pdfs"
        store = PdfStore(store_dir)
        assert store.base_dir.exists()

    def test_正常系_ソースディレクトリを取得できる(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path)
        source_dir = store.get_source_dir("blackrock")
        assert source_dir == tmp_path / "blackrock"
        assert source_dir.exists()

    def test_正常系_PDFファイルをリストできる(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path)
        source_dir = store.get_source_dir("test")
        (source_dir / "report1.pdf").write_bytes(b"pdf1")
        (source_dir / "report2.pdf").write_bytes(b"pdf2")
        (source_dir / "notes.txt").write_text("not a pdf")

        pdfs = store.list_pdfs("test")
        assert len(pdfs) == 2
        assert all(p.suffix == ".pdf" for p in pdfs)

    def test_正常系_存在しないソースで空リスト(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path)
        assert store.list_pdfs("nonexistent") == []

    def test_正常系_PDFの存在チェック(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path)
        source_dir = store.get_source_dir("test")
        (source_dir / "report.pdf").write_bytes(b"pdf")

        assert store.has_pdf("test", "report.pdf") is True
        assert store.has_pdf("test", "missing.pdf") is False

    def test_正常系_合計サイズを計算できる(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path)
        source_dir = store.get_source_dir("test")
        (source_dir / "a.pdf").write_bytes(b"x" * 100)
        (source_dir / "b.pdf").write_bytes(b"y" * 200)

        total = store.get_total_size("test")
        assert total == 300

    def test_正常系_ソースのPDFをクリーンアップできる(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path)
        source_dir = store.get_source_dir("test")
        (source_dir / "a.pdf").write_bytes(b"x")
        (source_dir / "b.pdf").write_bytes(b"y")

        removed = store.cleanup_source("test")
        assert removed == 2
        assert store.list_pdfs("test") == []

    @pytest.mark.asyncio
    async def test_正常系_download_and_storeでPDFを保存できる(
        self, tmp_path: Path
    ) -> None:
        store = PdfStore(tmp_path)
        expected_path = tmp_path / "test_source" / "report.pdf"
        expected_meta = PdfMetadata(
            url="https://example.com/report.pdf",
            local_path=expected_path,
            size_bytes=1024,
        )

        mock_downloader = AsyncMock()
        mock_downloader.download.return_value = expected_meta

        result = await store.download_and_store(
            mock_downloader,
            "https://example.com/report.pdf",
            "test_source",
        )

        assert result == expected_meta
        mock_downloader.download.assert_called_once_with(
            "https://example.com/report.pdf",
            tmp_path / "test_source",
            filename=None,
        )
