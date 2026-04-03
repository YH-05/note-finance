"""LiteParse-based PDF text extraction for the convert-pdf pipeline.

Extracts text from PDFs using LiteParse (local, Node.js-based) and
outputs page-level text as JSON for downstream Markdown structuring.

Usage
-----
    # Extract text
    uv run python scripts/liteparse_convert.py /path/to/report.pdf

    # With output directory
    uv run python scripts/liteparse_convert.py -o /output/dir /path/to/report.pdf

    # Disable OCR
    uv run python scripts/liteparse_convert.py --no-ocr /path/to/report.pdf
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def extract_text(
    pdf_path: Path,
    output_dir: Path | None = None,
    *,
    ocr_enabled: bool = True,
    dpi: int = 150,
) -> dict:
    """Extract text from a PDF using LiteParse.

    Parameters
    ----------
    pdf_path : Path
        Path to the PDF file.
    output_dir : Path | None
        Output directory for page_texts.json. Defaults to pdf_path's parent.
    ocr_enabled : bool
        Whether to enable OCR for scanned pages.
    dpi : int
        DPI for OCR processing.

    Returns
    -------
    dict
        Result metadata including page count and character count.
    """
    try:
        from liteparse import LiteParse
    except ImportError:
        msg = (
            "liteparse is not installed. "
            "Install with: uv add liteparse\n"
            "Also requires: Node.js 18+"
        )
        raise RuntimeError(msg)

    if not pdf_path.exists():
        msg = f"PDF ファイルが見つかりません: {pdf_path}"
        raise FileNotFoundError(msg)

    if output_dir is None:
        output_dir = pdf_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Extracting text with LiteParse: %s (ocr=%s, dpi=%d)",
        pdf_path.name,
        ocr_enabled,
        dpi,
    )

    parser = LiteParse()
    result = parser.parse(str(pdf_path), ocr_enabled=ocr_enabled, dpi=dpi)

    # Build page-level text dict
    page_texts: dict[str, str] = {}
    if hasattr(result, "pages"):
        for i, page in enumerate(result.pages):
            page_texts[str(i + 1)] = page.text
    else:
        # Fallback: single text block
        page_texts["1"] = result.text

    # Save page_texts.json
    page_texts_path = output_dir / "page_texts.json"
    page_texts_path.write_text(
        json.dumps(page_texts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        "page_texts.json saved: %s (%d pages)", page_texts_path, len(page_texts)
    )

    total_chars = sum(len(t) for t in page_texts.values())

    return {
        "status": "success",
        "pdf": str(pdf_path),
        "output_dir": str(output_dir),
        "page_texts_json": str(page_texts_path),
        "pages": len(page_texts),
        "total_chars": total_chars,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for liteparse_convert."""
    parser = argparse.ArgumentParser(
        description="LiteParse で PDF からテキストを抽出",
    )
    parser.add_argument(
        "pdf_path",
        type=Path,
        help="変換対象の PDF ファイルパス",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="出力ディレクトリ（省略時は PDF と同階層）",
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="OCR を無効化",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="OCR 解像度 (default: 150)",
    )
    args = parser.parse_args()

    try:
        result = extract_text(
            args.pdf_path,
            args.output_dir,
            ocr_enabled=not args.no_ocr,
            dpi=args.dpi,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.error("Extraction failed: %s", e)
        print(json.dumps({"status": "error", "error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
