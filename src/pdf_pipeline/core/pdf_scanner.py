"""PDF directory scanner with SHA-256 hash calculation.

Scans an input directory for PDF files, computes their SHA-256 hashes,
and identifies unprocessed files by comparing against known hashes.

Classes
-------
PdfScanner
    Scans a directory for PDF files and computes their SHA-256 hashes.

Functions
---------
compute_sha256_standalone
    Compute SHA-256 hash of a file without ``PdfScanner`` instantiation.

Examples
--------
>>> from pathlib import Path
>>> scanner = PdfScanner(Path("data/raw/pdfs"))
>>> results = scanner.scan_with_hashes()
>>> for path, sha256 in results:
...     print(f"{path.name}: {sha256[:8]}...")
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from pdf_pipeline._logging import get_logger
from pdf_pipeline.exceptions import PathTraversalError, ScanError

logger = get_logger(__name__, module="pdf_scanner")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HASH_BUFFER_SIZE = 65536  # 64 KiB read buffer for large files


def _compute_sha256_from_path(resolved: Path) -> str:
    """Compute SHA-256 digest from a resolved file path.

    Shared implementation used by both :meth:`PdfScanner.compute_sha256`
    and :func:`compute_sha256_standalone` to guarantee identical digests.

    Parameters
    ----------
    resolved : Path
        Resolved (absolute) path to the file to hash.

    Returns
    -------
    str
        Lowercase hexadecimal SHA-256 digest (64 characters).

    Raises
    ------
    OSError
        If the file cannot be read.
    """
    sha256 = hashlib.sha256()
    with resolved.open("rb") as fh:
        while chunk := fh.read(_HASH_BUFFER_SIZE):
            sha256.update(chunk)
    return sha256.hexdigest()


# ---------------------------------------------------------------------------
# PdfScanner class
# ---------------------------------------------------------------------------


class PdfScanner:
    """Scanner for PDF files in a directory with SHA-256 hash computation.

    Scans a single flat directory (non-recursive) for ``.pdf`` files,
    computes their SHA-256 hashes, and provides utilities to identify
    unprocessed files.

    Parameters
    ----------
    input_dir : Path
        Directory to scan for PDF files. Must exist and be a directory.

    Raises
    ------
    ScanError
        If ``input_dir`` does not exist or is not a directory.

    Examples
    --------
    >>> from pathlib import Path
    >>> scanner = PdfScanner(Path("data/raw/pdfs"))
    >>> scanner.input_dir
    PosixPath('data/raw/pdfs')
    """

    def __init__(self, input_dir: Path) -> None:
        """Initialize PdfScanner with an input directory.

        Parameters
        ----------
        input_dir : Path
            Directory to scan for PDF files.

        Raises
        ------
        ScanError
            If ``input_dir`` does not exist or is not a directory.
        """
        if not input_dir.exists():
            msg = f"Input directory does not exist: {input_dir}"
            logger.error(msg, path=str(input_dir))
            raise ScanError(msg, path=str(input_dir))

        if not input_dir.is_dir():
            msg = f"Input path is not a directory: {input_dir}"
            logger.error(msg, path=str(input_dir))
            raise ScanError(msg, path=str(input_dir))

        self.input_dir = input_dir
        logger.debug("PdfScanner initialized", input_dir=str(input_dir))

    def scan(self) -> list[Path]:
        """Scan the input directory for PDF files (non-recursive).

        Returns only ``.pdf`` files at the top level of ``input_dir``,
        sorted by filename.

        Returns
        -------
        list[Path]
            Sorted list of PDF file paths found in ``input_dir``.

        Examples
        --------
        >>> scanner = PdfScanner(Path("data/raw/pdfs"))
        >>> pdfs = scanner.scan()
        >>> all(p.suffix == ".pdf" for p in pdfs)
        True
        """
        pdfs = sorted(
            p for p in self.input_dir.iterdir() if p.is_file() and p.suffix == ".pdf"
        )
        logger.info(
            "PDF scan completed",
            input_dir=str(self.input_dir),
            count=len(pdfs),
        )
        return pdfs

    def compute_sha256(self, pdf_path: Path) -> str:
        """Compute the SHA-256 hash of a PDF file.

        Reads the file in 64 KiB chunks to handle large files efficiently.
        Validates that ``pdf_path`` is within ``input_dir`` to prevent
        path traversal attacks.

        Parameters
        ----------
        pdf_path : Path
            Path to the PDF file to hash.

        Returns
        -------
        str
            Lowercase hexadecimal SHA-256 digest (64 characters).

        Raises
        ------
        PathTraversalError
            If ``pdf_path`` resolves outside ``input_dir``.
        ScanError
            If the file does not exist or cannot be read.

        Examples
        --------
        >>> scanner = PdfScanner(Path("data/raw/pdfs"))
        >>> sha256 = scanner.compute_sha256(Path("data/raw/pdfs/report.pdf"))
        >>> len(sha256)
        64
        """
        # Path traversal protection
        try:
            resolved = pdf_path.resolve()
            base_resolved = self.input_dir.resolve()
        except OSError as exc:
            msg = f"Cannot resolve path: {pdf_path}"
            logger.error(msg, path=str(pdf_path))
            raise ScanError(msg, path=str(pdf_path)) from exc

        if not resolved.is_relative_to(base_resolved):
            msg = f"Path traversal detected: {pdf_path} is outside {self.input_dir}"
            logger.error(
                msg,
                path=str(pdf_path),
                base_dir=str(self.input_dir),
            )
            raise PathTraversalError(
                msg,
                path=str(pdf_path),
                base_dir=str(self.input_dir),
            )

        if not resolved.exists():
            msg = f"PDF file not found: {pdf_path}"
            logger.error(msg, path=str(pdf_path))
            raise ScanError(msg, path=str(pdf_path))

        try:
            digest = _compute_sha256_from_path(resolved)
        except OSError as exc:
            msg = f"Failed to read PDF for hashing: {pdf_path}: {exc}"
            logger.error(msg, path=str(pdf_path), error=str(exc))
            raise ScanError(msg, path=str(pdf_path)) from exc

        logger.debug(
            "SHA-256 computed",
            path=str(pdf_path),
            sha256=digest[:16] + "...",
        )
        return digest

    def scan_with_hashes(self) -> list[tuple[Path, str]]:
        """Scan the directory and compute SHA-256 hashes for all PDFs.

        Combines :meth:`scan` and :meth:`compute_sha256` to return
        ``(path, sha256)`` pairs for every PDF found.

        Returns
        -------
        list[tuple[Path, str]]
            List of ``(pdf_path, sha256_hex)`` pairs, sorted by path.

        Examples
        --------
        >>> scanner = PdfScanner(Path("data/raw/pdfs"))
        >>> for path, sha256 in scanner.scan_with_hashes():
        ...     print(f"{path.name}: {sha256[:8]}...")
        """
        pdfs = self.scan()
        results: list[tuple[Path, str]] = []

        for pdf_path in pdfs:
            sha256 = self.compute_sha256(pdf_path)
            results.append((pdf_path, sha256))

        logger.info(
            "Scan with hashes completed",
            input_dir=str(self.input_dir),
            count=len(results),
        )
        return results

    def find_unprocessed(
        self,
        processed_hashes: set[str],
    ) -> list[tuple[Path, str]]:
        """Find PDF files that have not yet been processed.

        Scans the directory, computes hashes, and filters out any
        files whose SHA-256 hash appears in ``processed_hashes``.

        Parameters
        ----------
        processed_hashes : set[str]
            Set of SHA-256 hashes for already-processed PDFs.

        Returns
        -------
        list[tuple[Path, str]]
            List of ``(pdf_path, sha256_hex)`` pairs for unprocessed PDFs,
            sorted by path.

        Examples
        --------
        >>> scanner = PdfScanner(Path("data/raw/pdfs"))
        >>> unprocessed = scanner.find_unprocessed(processed_hashes=set())
        >>> len(unprocessed) >= 0
        True
        """
        all_pdfs = self.scan_with_hashes()
        unprocessed = [
            (path, sha256)
            for path, sha256 in all_pdfs
            if sha256 not in processed_hashes
        ]

        logger.info(
            "Unprocessed PDFs identified",
            total=len(all_pdfs),
            unprocessed=len(unprocessed),
            already_processed=len(all_pdfs) - len(unprocessed),
        )
        return unprocessed


# ---------------------------------------------------------------------------
# Standalone utility
# ---------------------------------------------------------------------------


def compute_sha256_standalone(pdf_path: str) -> str:
    """Compute the SHA-256 hash of a file without ``PdfScanner`` instantiation.

    A lightweight alternative to :meth:`PdfScanner.compute_sha256` that
    does **not** require directory-level instantiation or path traversal
    validation.  The caller is responsible for ensuring the path is safe.

    Uses the same hash algorithm (SHA-256) and buffer size (64 KiB) as
    ``PdfScanner.compute_sha256`` to guarantee identical digests for the
    same file content.

    Parameters
    ----------
    pdf_path : str
        Absolute or relative path to the file to hash.

    Returns
    -------
    str
        Lowercase hexadecimal SHA-256 digest (64 characters).

    Raises
    ------
    ScanError
        If the file does not exist or cannot be read.

    Examples
    --------
    >>> digest = compute_sha256_standalone("/data/raw/pdfs/report.pdf")
    >>> len(digest)
    64
    """
    resolved = Path(pdf_path).resolve()

    if not resolved.exists():
        msg = f"PDF file not found: {pdf_path}"
        logger.error(msg, path=pdf_path)
        raise ScanError(msg, path=pdf_path)

    try:
        digest = _compute_sha256_from_path(resolved)
    except OSError as exc:
        msg = f"Failed to read file for hashing: {pdf_path}: {exc}"
        logger.error(msg, path=pdf_path, error=str(exc))
        raise ScanError(msg, path=pdf_path) from exc

    logger.debug(
        "SHA-256 computed (standalone)",
        path=pdf_path,
        sha256=digest[:16] + "...",
    )
    return digest
