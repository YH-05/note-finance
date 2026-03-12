"""Table detection from PDF pages using PyMuPDF.

Extracts table regions from PDF documents using the pymupdf ``find_tables``
method, crops each region to a PNG image, and returns a list of
:class:`~pdf_pipeline.schemas.tables.RawTable` instances with cell data and
bounding-box metadata.

Classes
-------
TableDetector
    Detects and extracts table regions from a PDF file.

Examples
--------
>>> detector = TableDetector()
>>> raw_tables = detector.detect("data/raw/report.pdf")
>>> len(raw_tables) >= 0
True
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from pdf_pipeline._logging import get_logger
from pdf_pipeline.exceptions import PdfPipelineError
from pdf_pipeline.schemas.tables import RawTable, TableCell

logger = get_logger(__name__, module="table_detector")

# Default output directory for cropped table images
_DEFAULT_OUTPUT_DIR = Path(".tmp/table_images")


class TableDetector:
    """Detects table regions in a PDF and extracts them as images and metadata.

    Uses PyMuPDF's ``find_tables`` to locate table bounding boxes on each
    page, saves a cropped PNG for each table, and returns a list of
    :class:`~pdf_pipeline.schemas.tables.RawTable` instances.

    Parameters
    ----------
    output_dir : Path | None
        Directory in which to save cropped table PNG files.
        Defaults to ``.tmp/table_images`` in the current working directory.

    Examples
    --------
    >>> from pathlib import Path
    >>> detector = TableDetector(output_dir=Path("/tmp/tables"))
    >>> detector.output_dir
    PosixPath('/tmp/tables')
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        """Initialize TableDetector with an output directory.

        Parameters
        ----------
        output_dir : Path | None
            Directory to save table PNG images.  Created on first use.
        """
        self.output_dir = output_dir or _DEFAULT_OUTPUT_DIR
        logger.debug(
            "TableDetector initialized",
            output_dir=str(self.output_dir),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self,
        pdf_path: str,
        doc: fitz.Document | None = None,
    ) -> list[RawTable]:
        """Detect tables in a PDF and return Tier-1 RawTable objects.

        Opens the PDF (or reuses a pre-opened document), iterates over
        each page, locates tables using ``page.find_tables()``, crops each
        region to a PNG, and populates a
        :class:`~pdf_pipeline.schemas.tables.RawTable` for each.

        Parameters
        ----------
        pdf_path : str
            Path to the PDF file to process.
        doc : fitz.Document | None
            Optional pre-opened ``fitz.Document``.  When provided the
            method uses it directly and **does not close it** — the caller
            retains ownership.  When ``None`` (default) the method opens
            the file itself and closes it before returning.

        Returns
        -------
        list[RawTable]
            List of :class:`~pdf_pipeline.schemas.tables.RawTable` instances,
            one per detected table.  Returns an empty list if no tables are
            found.

        Raises
        ------
        PdfPipelineError
            If the PDF cannot be opened or processed.

        Examples
        --------
        >>> detector = TableDetector()
        >>> raw_tables = detector.detect("report.pdf")
        >>> isinstance(raw_tables, list)
        True
        """
        logger.info("Starting table detection", pdf_path=pdf_path)
        raw_tables: list[RawTable] = []

        caller_owns_doc = doc is not None
        if doc is None:
            try:
                doc = fitz.open(pdf_path)
            except Exception as exc:
                msg = f"Failed to open PDF for table detection: {pdf_path}"
                logger.error(msg, error=str(exc))
                raise PdfPipelineError(msg) from exc

        try:
            for page in doc:
                page_tables = self._process_page(page, pdf_path=pdf_path)
                raw_tables.extend(page_tables)
        finally:
            if not caller_owns_doc:
                doc.close()

        logger.info(
            "Table detection complete",
            pdf_path=pdf_path,
            table_count=len(raw_tables),
        )
        return raw_tables

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _process_page(self, page: fitz.Page, *, pdf_path: str) -> list[RawTable]:
        """Process a single PDF page and extract tables.

        Parameters
        ----------
        page : fitz.Page
            The pymupdf page object.
        pdf_path : str
            Source PDF path (used for logging).

        Returns
        -------
        list[RawTable]
            Tables found on this page, as RawTable instances.
        """
        page_number_1based = int(page.number) + 1  # type: ignore[arg-type]  # pymupdf uses 0-based indexing
        finder = page.find_tables()  # type: ignore[attr-defined]
        if not finder.tables:
            logger.debug(
                "No tables found on page",
                page=page_number_1based,
                pdf_path=pdf_path,
            )
            return []

        result: list[RawTable] = []
        for table_idx, table in enumerate(finder.tables):
            raw = self._extract_table(
                page=page,
                table=table,
                page_number=page_number_1based,
                table_idx=table_idx,
            )
            result.append(raw)

        logger.debug(
            "Tables extracted from page",
            page=page_number_1based,
            count=len(result),
        )
        return result

    def _extract_table(
        self,
        *,
        page: fitz.Page,
        table: Any,
        page_number: int,
        table_idx: int,
    ) -> RawTable:
        """Extract a single table from a page.

        Crops the table region to a PNG, converts pymupdf cells to
        :class:`~pdf_pipeline.schemas.tables.TableCell` objects, and builds a
        :class:`~pdf_pipeline.schemas.tables.RawTable`.

        Parameters
        ----------
        page : fitz.Page
            The pymupdf page object.
        table : fitz table object
            The detected table from pymupdf (``TableFinder.tables[i]``).
        page_number : int
            1-based page number.
        table_idx : int
            0-based table index within the page.

        Returns
        -------
        RawTable
            Populated Tier-1 raw table instance.
        """
        bbox_raw = table.bbox
        bbox = [
            float(bbox_raw[0]),
            float(bbox_raw[1]),
            float(bbox_raw[2]),
            float(bbox_raw[3]),
        ]

        # Save table image crop
        image_path = self._save_table_image(
            page=page,
            bbox=bbox,
            page_number=page_number,
            table_idx=table_idx,
        )

        # Convert pymupdf cells → TableCell
        cells = self._convert_cells(table.cells)

        # Convert header cells → multi-level header rows
        headers = self._convert_headers(table.header.cells)

        raw = RawTable(
            page_number=page_number,
            bbox=bbox,
            cells=cells,
            headers=headers,
            image_path=image_path,
        )
        logger.debug(
            "RawTable created",
            page=page_number,
            table_idx=table_idx,
            cell_count=len(cells),
            image_path=image_path,
        )
        return raw

    def _save_table_image(
        self,
        *,
        page: fitz.Page,
        bbox: list[float],
        page_number: int,
        table_idx: int,
    ) -> str:
        """Crop and save the table region as a PNG image.

        Parameters
        ----------
        page : fitz.Page
            The pymupdf page from which to crop.
        bbox : list[float]
            [x0, y0, x1, y1] bounding box of the table.
        page_number : int
            1-based page number for file naming.
        table_idx : int
            0-based table index for file naming.

        Returns
        -------
        str
            Absolute path to the saved PNG file.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        unique_id = uuid.uuid4().hex[:8]
        filename = f"table_p{page_number}_t{table_idx}_{unique_id}.png"
        image_path = self.output_dir / filename

        clip_rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
        pixmap = page.get_pixmap(clip=clip_rect)
        pixmap.save(str(image_path))

        logger.debug("Table image saved", path=str(image_path))
        return str(image_path)

    def _convert_cells(self, raw_cells: list) -> list[TableCell]:
        """Convert pymupdf cell objects to TableCell instances.

        Parameters
        ----------
        raw_cells : list
            List of pymupdf cell objects from ``table.cells``.

        Returns
        -------
        list[TableCell]
            Converted TableCell instances.  Falls back to a single placeholder
            cell if the cell list is empty or all cells fail conversion.
        """
        cells: list[TableCell] = []
        for raw_cell in raw_cells:
            try:
                cell = TableCell(
                    row=int(raw_cell.row),
                    col=int(raw_cell.col),
                    value=str(raw_cell.text) if raw_cell.text is not None else "",
                    rowspan=int(raw_cell.rowspan) if raw_cell.rowspan else 1,
                    colspan=int(raw_cell.colspan) if raw_cell.colspan else 1,
                    is_header=False,
                )
                cells.append(cell)
            except Exception as exc:
                logger.warning("Failed to convert cell", error=str(exc))

        if not cells:
            # Fallback: at least one placeholder cell to satisfy RawTable.cells min_length
            cells.append(TableCell(row=0, col=0, value=""))

        return cells

    def _convert_headers(self, raw_header_cells: list) -> list[list[TableCell]]:
        """Convert pymupdf header cells to multi-level header rows.

        Groups header cells by their ``row`` attribute to build
        ``list[list[TableCell]]`` compatible with ``RawTable.headers``.

        Parameters
        ----------
        raw_header_cells : list
            List of pymupdf header cell objects.

        Returns
        -------
        list[list[TableCell]]
            Multi-level header rows.  Empty list if no header cells.
        """
        if not raw_header_cells:
            return []

        # Group cells by row index
        row_map: dict[int, list[TableCell]] = {}
        for raw_cell in raw_header_cells:
            try:
                row_idx = int(raw_cell.row)
                cell = TableCell(
                    row=row_idx,
                    col=int(raw_cell.col),
                    value=str(raw_cell.text) if raw_cell.text is not None else "",
                    rowspan=int(raw_cell.rowspan) if raw_cell.rowspan else 1,
                    colspan=int(raw_cell.colspan) if raw_cell.colspan else 1,
                    is_header=True,
                )
                row_map.setdefault(row_idx, []).append(cell)
            except Exception as exc:
                logger.warning("Failed to convert header cell", error=str(exc))

        return [row_map[k] for k in sorted(row_map)]
