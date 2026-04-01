"""PyMuPDF-based PDF pre-scanner for the convert-pdf pipeline.

Extracts structural information (image locations, text tables, page text
density) to guide the auto method selection and Vision read targeting.

Usage
-----
    $ uv run python -m pdf_pipeline.cli.prescan_pdf /path/to/report.pdf
    {"pages": 20, "table_ratio": 0.15, "image_ratio": 0.4, ...}

    $ uv run python -m pdf_pipeline.cli.prescan_pdf /path/to/report.pdf -o prescan.json
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

import fitz  # type: ignore[import-untyped]

from pdf_pipeline._logging import get_logger

logger = get_logger(__name__, module="cli.prescan_pdf")

# ---------------------------------------------------------------------------
# Thresholds for image classification
# ---------------------------------------------------------------------------

LARGE_IMAGE_WIDTH_RATIO = 0.4  # ページ幅の40%以上
LARGE_IMAGE_AREA_RATIO = 0.1  # ページ面積の10%以上


def prescan(pdf_path: str) -> dict:
    """Pre-scan a PDF for structural complexity.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.

    Returns
    -------
    dict
        Scan results including page-level image/table info and
        aggregate ratios.
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    pages_with_tables = 0
    pages_with_images = 0
    pages_with_large_images = 0
    total_tables = 0
    total_images = 0
    page_details: list[dict] = []

    for i, page in enumerate(doc):  # type: ignore[arg-type]
        page_width = page.rect.width
        page_area = page.rect.width * page.rect.height

        # Detect text-based tables (suppress PyMuPDF pymupdf_layout promo)
        with contextlib.redirect_stdout(io.StringIO()):
            tables = page.find_tables()
        table_count = len(tables.tables) if tables.tables else 0
        if table_count > 0:
            pages_with_tables += 1
            total_tables += table_count

        # Detect images
        images = page.get_images()
        image_count = len(images)
        has_large_image = False

        if image_count > 0:
            pages_with_images += 1
            total_images += image_count

            for img in images:
                xref = img[0]
                rects = page.get_image_rects(xref)
                if not rects:
                    continue
                rect = rects[0]
                width_ratio = rect.width / page_width if page_width > 0 else 0
                area_ratio = (
                    (rect.width * rect.height) / page_area if page_area > 0 else 0
                )
                if (
                    width_ratio >= LARGE_IMAGE_WIDTH_RATIO
                    and area_ratio >= LARGE_IMAGE_AREA_RATIO
                ):
                    has_large_image = True
                    break

        if has_large_image:
            pages_with_large_images += 1

        page_details.append(
            {
                "page": i + 1,
                "text_tables": table_count,
                "images": image_count,
                "has_large_image": has_large_image,
            }
        )

    doc.close()

    result = {
        "pages": total_pages,
        "table_ratio": pages_with_tables / total_pages if total_pages else 0,
        "image_ratio": pages_with_images / total_pages if total_pages else 0,
        "large_image_ratio": pages_with_large_images / total_pages
        if total_pages
        else 0,
        "total_tables": total_tables,
        "total_images": total_images,
        "page_details": page_details,
    }

    logger.info(
        "Prescan complete",
        pages=total_pages,
        table_ratio=f"{result['table_ratio']:.2f}",
        image_ratio=f"{result['image_ratio']:.2f}",
        large_image_ratio=f"{result['large_image_ratio']:.2f}",
    )

    return result


def vision_target_pages(
    page_details: list[dict],
    disclaimer_pages: list[int] | None = None,
) -> list[int]:
    """Identify pages that need Claude Vision reads.

    A page needs Vision if it has a large image (potential table-as-image).
    Disclaimer pages are excluded.

    Parameters
    ----------
    page_details : list[dict]
        Per-page scan details from ``prescan()``.
    disclaimer_pages : list[int] | None
        Pages to exclude (disclaimers).

    Returns
    -------
    list[int]
        Page numbers requiring Vision read.
    """
    excluded = set(disclaimer_pages or [])
    return [
        pd["page"]
        for pd in page_details
        if pd["has_large_image"] and pd["page"] not in excluded
    ]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for prescan_pdf."""
    if len(sys.argv) < 2:
        print(
            "Usage: python -m pdf_pipeline.cli.prescan_pdf <pdf_path> [-o output.json]",
            file=sys.stderr,
        )
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_path = None
    if "-o" in sys.argv:
        idx = sys.argv.index("-o")
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]

    try:
        result = prescan(pdf_path)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    result_json = json.dumps(result, ensure_ascii=False, indent=2)

    if output_path:
        Path(output_path).write_text(result_json, encoding="utf-8")
        print(f"Saved to {output_path}", file=sys.stderr)

    print(result_json)


if __name__ == "__main__":
    main()
