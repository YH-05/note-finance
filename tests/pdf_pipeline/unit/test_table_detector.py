"""Unit tests for pdf_pipeline.core.table_detector module.

Tests cover:
- TableDetector extracts table regions from PDFs using pymupdf
- Metadata JSON generation (page number, bounding box)
- Returns list of RawTable with image_path set
- Edge cases: no tables found, invalid PDF path
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from pdf_pipeline.core.table_detector import TableDetector
from pdf_pipeline.exceptions import PdfPipelineError
from pdf_pipeline.schemas.tables import RawTable


class TestTableDetector:
    """Tests for TableDetector class."""

    def test_正常系_インスタンス生成できる(self, tmp_path: Path) -> None:
        detector = TableDetector(output_dir=tmp_path)
        assert detector.output_dir == tmp_path

    def test_正常系_output_dirのデフォルト値が設定される(self) -> None:
        detector = TableDetector()
        assert detector.output_dir is not None

    def test_正常系_テーブルなしPDFで空リストを返す(self, tmp_path: Path) -> None:
        """When a PDF has no detected tables, returns an empty list."""
        detector = TableDetector(output_dir=tmp_path)
        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.find_tables.return_value.tables = []

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("pdf_pipeline.core.table_detector.fitz.open", return_value=mock_doc):
            result = detector.detect("dummy.pdf")

        assert result == []

    def test_正常系_テーブルを検出してRawTableリストを返す(
        self, tmp_path: Path
    ) -> None:
        """When a PDF page has tables, returns RawTable instances."""
        detector = TableDetector(output_dir=tmp_path)

        # Mock a table with cells
        mock_cell = MagicMock()
        mock_cell.text = "Revenue"
        mock_cell.col = 0
        mock_cell.row = 0
        mock_cell.rowspan = 1
        mock_cell.colspan = 1

        mock_table = MagicMock()
        mock_table.bbox = (10.0, 20.0, 200.0, 100.0)
        mock_table.cells = [mock_cell]
        mock_table.header.cells = []

        mock_finder = MagicMock()
        mock_finder.tables = [mock_table]

        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.find_tables.return_value = mock_finder
        mock_page.get_pixmap.return_value = MagicMock(**{"save": MagicMock()})

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("pdf_pipeline.core.table_detector.fitz.open", return_value=mock_doc):
            result = detector.detect("dummy.pdf")

        assert len(result) == 1
        assert isinstance(result[0], RawTable)
        assert result[0].page_number == 1
        assert result[0].bbox == [10.0, 20.0, 200.0, 100.0]

    def test_正常系_検出した表のimage_pathが設定される(self, tmp_path: Path) -> None:
        """image_path is set on each returned RawTable."""
        detector = TableDetector(output_dir=tmp_path)

        mock_cell = MagicMock()
        mock_cell.text = "FY2024"
        mock_cell.col = 0
        mock_cell.row = 0
        mock_cell.rowspan = 1
        mock_cell.colspan = 1

        mock_table = MagicMock()
        mock_table.bbox = (5.0, 10.0, 150.0, 80.0)
        mock_table.cells = [mock_cell]
        mock_table.header.cells = []

        mock_finder = MagicMock()
        mock_finder.tables = [mock_table]

        mock_pixmap = MagicMock()
        mock_pixmap.save = MagicMock()

        mock_page = MagicMock()
        mock_page.number = 2
        mock_page.find_tables.return_value = mock_finder
        mock_page.get_pixmap.return_value = mock_pixmap

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("pdf_pipeline.core.table_detector.fitz.open", return_value=mock_doc):
            result = detector.detect("dummy.pdf")

        assert result[0].image_path is not None
        assert result[0].image_path.endswith(".png")

    def test_正常系_複数ページ複数テーブルを検出できる(self, tmp_path: Path) -> None:
        """Multiple tables across multiple pages are all returned."""
        detector = TableDetector(output_dir=tmp_path)

        def _make_page_with_n_tables(page_number: int, n: int) -> MagicMock:
            tables = []
            for i in range(n):
                mock_cell = MagicMock()
                mock_cell.text = f"cell_{i}"
                mock_cell.col = 0
                mock_cell.row = 0
                mock_cell.rowspan = 1
                mock_cell.colspan = 1
                t = MagicMock()
                t.bbox = (0.0, float(i * 50), 100.0, float((i + 1) * 50))
                t.cells = [mock_cell]
                t.header.cells = []
                tables.append(t)
            finder = MagicMock()
            finder.tables = tables
            page = MagicMock()
            page.number = page_number
            page.find_tables.return_value = finder
            page.get_pixmap.return_value = MagicMock(**{"save": MagicMock()})
            return page

        pages = [_make_page_with_n_tables(0, 2), _make_page_with_n_tables(1, 1)]
        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter(pages))
        mock_doc.__len__ = MagicMock(return_value=2)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("pdf_pipeline.core.table_detector.fitz.open", return_value=mock_doc):
            result = detector.detect("dummy.pdf")

        assert len(result) == 3

    def test_異常系_fitz_openが例外を投げるとPdfPipelineError(
        self, tmp_path: Path
    ) -> None:
        """If fitz.open raises, detect() raises PdfPipelineError."""
        detector = TableDetector(output_dir=tmp_path)

        with (
            patch(
                "pdf_pipeline.core.table_detector.fitz.open",
                side_effect=RuntimeError("bad pdf"),
            ),
            pytest.raises(PdfPipelineError),
        ):
            detector.detect("nonexistent.pdf")


class TestTableDetectorMetadata:
    """Tests for metadata JSON generation in TableDetector."""

    def test_正常系_メタデータに正しいページ番号とbboxが含まれる(
        self, tmp_path: Path
    ) -> None:
        detector = TableDetector(output_dir=tmp_path)

        mock_cell = MagicMock()
        mock_cell.text = "Test"
        mock_cell.col = 0
        mock_cell.row = 0
        mock_cell.rowspan = 1
        mock_cell.colspan = 1

        mock_table = MagicMock()
        mock_table.bbox = (0.0, 0.0, 300.0, 150.0)
        mock_table.cells = [mock_cell]
        mock_table.header.cells = []

        mock_finder = MagicMock()
        mock_finder.tables = [mock_table]

        mock_page = MagicMock()
        mock_page.number = 4
        mock_page.find_tables.return_value = mock_finder
        mock_page.get_pixmap.return_value = MagicMock(**{"save": MagicMock()})

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("pdf_pipeline.core.table_detector.fitz.open", return_value=mock_doc):
            result = detector.detect("dummy.pdf")

        raw = result[0]
        assert raw.page_number == 5  # page.number is 0-based → +1
        assert raw.bbox == [0.0, 0.0, 300.0, 150.0]
