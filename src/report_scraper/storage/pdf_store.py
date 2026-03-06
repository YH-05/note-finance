"""PDF file storage for the report_scraper package.

Manages PDF file storage organized by source key. PDFs are stored at
``{base_dir}/{source_key}/``. Integrates with ``PdfDownloader`` for
download-and-store workflows.

Classes
-------
PdfStore
    PDF file storage manager.

Examples
--------
>>> from pathlib import Path
>>> store = PdfStore(Path("data/raw/report-scraper/pdfs"))
>>> store.get_source_dir("blackrock")
PosixPath('data/raw/report-scraper/pdfs/blackrock')
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from report_scraper._logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from report_scraper.services.pdf_downloader import PdfDownloader
    from report_scraper.types import PdfMetadata

logger = get_logger(__name__, module="pdf_store")

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

DEFAULT_PDF_DIR = "data/raw/report-scraper/pdfs"
"""Default base directory for PDF storage."""

_SOURCE_KEY_RE = re.compile(r"^[a-zA-Z0-9_]+$")
"""Allowed characters for source_key: alphanumeric and underscore."""


# ---------------------------------------------------------------------------
# PdfStore class
# ---------------------------------------------------------------------------


class PdfStore:
    """PDF file storage manager organized by source key.

    Stores PDF files in ``{base_dir}/{source_key}/`` directories.
    Provides methods for listing stored PDFs, checking existence,
    and downloading new PDFs via ``PdfDownloader``.

    Parameters
    ----------
    base_dir : Path
        Root directory for PDF storage. Subdirectories per source
        are created automatically.

    Examples
    --------
    >>> from pathlib import Path
    >>> store = PdfStore(Path("/tmp/pdfs"))
    >>> store.base_dir
    PosixPath('/tmp/pdfs')
    """

    def __init__(self, base_dir: Path) -> None:
        """Initialize PdfStore and create base directory.

        Parameters
        ----------
        base_dir : Path
            Root directory for PDF storage.
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("PdfStore initialized", base_dir=str(base_dir))

    def get_source_dir(self, source_key: str) -> Path:
        """Get the storage directory for a specific source.

        Creates the directory if it does not exist.

        Parameters
        ----------
        source_key : str
            Unique source identifier.

        Returns
        -------
        Path
            Directory path for the source's PDFs.

        Raises
        ------
        ValueError
            If ``source_key`` resolves outside the base directory
            (path traversal protection).

        Examples
        --------
        >>> from pathlib import Path
        >>> store = PdfStore(Path("/tmp/pdfs"))
        >>> store.get_source_dir("blackrock")
        PosixPath('/tmp/pdfs/blackrock')
        """
        self._validate_source_key(source_key)
        source_dir = self.base_dir / source_key
        source_dir.mkdir(parents=True, exist_ok=True)
        return source_dir

    def _validate_source_key(self, source_key: str) -> None:
        """Validate source_key format and path safety.

        Raises
        ------
        ValueError
            If the source_key contains invalid characters or would
            resolve outside base_dir (path traversal).
        """
        if not _SOURCE_KEY_RE.match(source_key):
            raise ValueError(
                f"Invalid source_key (must be alphanumeric/underscore): {source_key}"
            )
        candidate = self.base_dir / source_key
        if not candidate.resolve().is_relative_to(self.base_dir.resolve()):
            raise ValueError(
                f"Invalid source_key (path traversal detected): {source_key}"
            )

    def list_pdfs(self, source_key: str) -> list[Path]:
        """List all PDF files for a given source.

        Parameters
        ----------
        source_key : str
            Source identifier.

        Returns
        -------
        list[Path]
            Sorted list of PDF file paths.
        """
        self._validate_source_key(source_key)
        source_dir = self.base_dir / source_key
        if not source_dir.exists():
            return []

        pdfs = sorted(source_dir.glob("*.pdf"))
        logger.debug(
            "Listed PDFs",
            source_key=source_key,
            count=len(pdfs),
        )
        return pdfs

    def has_pdf(self, source_key: str, filename: str) -> bool:
        """Check if a PDF file already exists for a source.

        Parameters
        ----------
        source_key : str
            Source identifier.
        filename : str
            PDF filename to check.

        Returns
        -------
        bool
            ``True`` if the file exists.
        """
        self._validate_source_key(source_key)
        return (self.base_dir / source_key / filename).exists()

    async def download_and_store(
        self,
        downloader: PdfDownloader,
        url: str,
        source_key: str,
        *,
        filename: str | None = None,
    ) -> PdfMetadata:
        """Download a PDF and store it in the source's directory.

        Parameters
        ----------
        downloader : PdfDownloader
            PDF downloader instance to use.
        url : str
            URL of the PDF to download.
        source_key : str
            Source identifier for directory organization.
        filename : str | None
            Optional filename override.

        Returns
        -------
        PdfMetadata
            Metadata about the downloaded and stored PDF.

        Raises
        ------
        FetchError
            If the download fails.
        """
        output_dir = self.get_source_dir(source_key)

        logger.info(
            "Downloading and storing PDF",
            source_key=source_key,
            url=url,
            output_dir=str(output_dir),
        )

        pdf_meta = await downloader.download(
            url,
            output_dir,
            filename=filename,
        )

        logger.info(
            "PDF stored successfully",
            source_key=source_key,
            url=url,
            path=str(pdf_meta.local_path),
            size_bytes=pdf_meta.size_bytes,
        )

        return pdf_meta

    def get_total_size(self, source_key: str) -> int:
        """Get the total size of all PDFs for a source in bytes.

        Parameters
        ----------
        source_key : str
            Source identifier.

        Returns
        -------
        int
            Total size in bytes.
        """
        pdfs = self.list_pdfs(source_key)
        total = sum(p.stat().st_size for p in pdfs)
        logger.debug(
            "Total PDF size calculated",
            source_key=source_key,
            total_bytes=total,
            file_count=len(pdfs),
        )
        return total

    def cleanup_source(self, source_key: str) -> int:
        """Remove all PDF files for a source.

        Parameters
        ----------
        source_key : str
            Source identifier.

        Returns
        -------
        int
            Number of files removed.
        """
        pdfs = self.list_pdfs(source_key)
        removed = 0
        for pdf_path in pdfs:
            try:
                pdf_path.unlink()
                removed += 1
            except OSError as exc:
                logger.warning(
                    "Failed to remove PDF",
                    path=str(pdf_path),
                    error=str(exc),
                )

        logger.info(
            "Source PDFs cleaned up",
            source_key=source_key,
            removed=removed,
        )
        return removed
