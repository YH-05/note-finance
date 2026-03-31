"""Auto method preparation for the /convert-pdf pipeline.

Runs the deterministic, API-free stages of the auto conversion method:
  - ``prepare``: prescan + LiteParse text extraction
  - ``build_plan``: gap detection + content text assembly (given disclaimer pages)

The Haiku disclaimer classification (Stage B') is handled by the
/convert-pdf skill itself, which spawns a Haiku subagent via
``Agent(model="haiku")``. This module does NOT call any LLM API.

Usage
-----
    # Stage A+B: prescan + liteparse
    $ uv run python -m pdf_pipeline.cli.convert_auto prepare /path/to/report.pdf /out

    # Stage C: build plan with disclaimer pages
    $ uv run python -m pdf_pipeline.cli.convert_auto build_plan /out [5,6,7]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pdf_pipeline._logging import get_logger
from pdf_pipeline.cli.prescan_pdf import prescan, vision_target_pages

logger = get_logger(__name__, module="cli.convert_auto")


# ---------------------------------------------------------------------------
# Stage A+B: prescan + LiteParse (no API calls)
# ---------------------------------------------------------------------------


def _run_liteparse(
    pdf_path: str,
    output_dir: Path,
    *,
    ocr_enabled: bool,
    dpi: int,
) -> dict[str, str]:
    """Run LiteParse text extraction and return page texts.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.
    output_dir : Path
        Output directory for page_texts.json.
    ocr_enabled : bool
        Whether to enable OCR.
    dpi : int
        DPI for OCR processing.

    Returns
    -------
    dict[str, str]
        Page number (str) to text content mapping.
    """
    liteparse_args = ["uv", "run", "python", "scripts/liteparse_convert.py"]
    liteparse_args.extend(["-o", str(output_dir)])
    if not ocr_enabled:
        liteparse_args.append("--no-ocr")
    if dpi != 150:
        liteparse_args.extend(["--dpi", str(dpi)])
    liteparse_args.append(pdf_path)

    lp_result = subprocess.run(
        liteparse_args,
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        check=False,
    )
    if lp_result.returncode != 0:
        msg = f"LiteParse extraction failed: {lp_result.stderr}"
        logger.error(msg, stderr=lp_result.stderr)
        raise RuntimeError(msg)

    page_texts_path = output_dir / "page_texts.json"
    if not page_texts_path.exists():
        msg = "LiteParse did not produce page_texts.json"
        raise RuntimeError(msg)

    page_texts: dict[str, str] = json.loads(
        page_texts_path.read_text(encoding="utf-8"),
    )
    logger.info("LiteParse completed", pages=len(page_texts))
    return page_texts


def prepare(
    pdf_path: str,
    output_dir: str,
    *,
    ocr_enabled: bool = True,
    dpi: int = 150,
) -> dict:
    """Run Stage A (prescan) + Stage B (LiteParse). No API calls.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.
    output_dir : str
        Output directory for intermediate files.
    ocr_enabled : bool
        Whether to enable OCR in LiteParse.
    dpi : int
        DPI for OCR processing.

    Returns
    -------
    dict
        Intermediate result with prescan data and file paths.
    """
    pdf = Path(pdf_path)
    if not pdf.exists():
        msg = f"PDF ファイルが見つかりません: {pdf_path}"
        raise FileNotFoundError(msg)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Stage A: PyMuPDF prescan
    logger.info("Stage A: Running prescan", pdf_path=pdf_path)
    prescan_result = prescan(pdf_path)

    prescan_path = out / "prescan.json"
    prescan_path.write_text(
        json.dumps(prescan_result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        "Prescan saved",
        pages=prescan_result["pages"],
        table_ratio=f"{prescan_result['table_ratio']:.2f}",
        large_image_ratio=f"{prescan_result['large_image_ratio']:.2f}",
    )

    # Stage B: LiteParse text extraction
    logger.info("Stage B: Running LiteParse", pdf_path=pdf_path)
    _run_liteparse(pdf_path, out, ocr_enabled=ocr_enabled, dpi=dpi)

    result = {
        "pdf_path": str(pdf.resolve()),
        "output_dir": str(out.resolve()),
        "page_count": prescan_result["pages"],
        "prescan_path": str(prescan_path),
        "page_texts_path": str(out / "page_texts.json"),
    }

    logger.info("Prepare completed (Stage A+B)", pages=prescan_result["pages"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


# ---------------------------------------------------------------------------
# Stage C: build plan (given disclaimer pages from skill)
# ---------------------------------------------------------------------------


def build_plan(output_dir: str, disclaimer_pages_json: str = "[]") -> dict:
    """Build the conversion plan given disclaimer pages from the skill.

    Reads prescan.json and page_texts.json from ``output_dir``,
    computes vision target pages and content text.

    Parameters
    ----------
    output_dir : str
        Directory containing prescan.json and page_texts.json.
    disclaimer_pages_json : str
        JSON array of disclaimer page numbers (from Haiku classification).

    Returns
    -------
    dict
        Final plan with vision_pages, content_pages, content_text_path.
    """
    out = Path(output_dir)

    prescan_path = out / "prescan.json"
    prescan_result = json.loads(prescan_path.read_text(encoding="utf-8"))

    page_texts_path = out / "page_texts.json"
    page_texts: dict[str, str] = json.loads(
        page_texts_path.read_text(encoding="utf-8"),
    )

    disclaimer_pages: list[int] = json.loads(disclaimer_pages_json)
    page_count = prescan_result["pages"]

    # Stage C: gap detection
    vision_pages = vision_target_pages(
        prescan_result["page_details"],
        disclaimer_pages,
    )
    logger.info("Vision target pages", pages=vision_pages)

    # Content pages = all - disclaimers
    disclaimer_set = set(disclaimer_pages)
    content_pages = [p for p in range(1, page_count + 1) if p not in disclaimer_set]

    # Build content text
    parts = [
        page_texts.get(str(p), "").strip()
        for p in content_pages
        if page_texts.get(str(p), "").strip()
    ]
    content_text = "\n\n".join(parts)
    content_text_path = out / "content_text.txt"
    content_text_path.write_text(content_text, encoding="utf-8")

    plan = {
        "pdf_path": prescan_result.get("pdf_path", ""),
        "output_dir": str(out.resolve()),
        "page_count": page_count,
        "prescan": {
            "table_ratio": prescan_result["table_ratio"],
            "image_ratio": prescan_result["image_ratio"],
            "large_image_ratio": prescan_result["large_image_ratio"],
            "total_tables": prescan_result["total_tables"],
            "total_images": prescan_result["total_images"],
        },
        "disclaimer_pages": disclaimer_pages,
        "vision_pages": vision_pages,
        "content_pages": content_pages,
        "content_text_path": str(content_text_path),
        "content_text_chars": len(content_text),
        "page_texts_path": str(page_texts_path),
        "prescan_path": str(prescan_path),
    }

    plan_path = out / "plan.json"
    plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        "Plan saved",
        vision_pages=len(vision_pages),
        content_pages=len(content_pages),
        disclaimer_pages=len(disclaimer_pages),
    )

    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return plan


# ---------------------------------------------------------------------------
# CLI dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "prepare": None,  # handled in main() with extra args
    "build_plan": None,
}


def main() -> None:
    """CLI entry point for convert_auto."""
    if len(sys.argv) < 2 or sys.argv[1] not in _DISPATCH:
        print(
            "Usage:\n"
            "  python -m pdf_pipeline.cli.convert_auto prepare <pdf> <out> [--no-ocr] [--dpi N]\n"
            "  python -m pdf_pipeline.cli.convert_auto build_plan <out> '[5,6,7]'",
            file=sys.stderr,
        )
        sys.exit(1)

    command = sys.argv[1]

    try:
        if command == "prepare":
            if len(sys.argv) < 4:
                print("Error: prepare requires <pdf_path> <output_dir>", file=sys.stderr)
                sys.exit(1)
            pdf_path = sys.argv[2]
            output_dir = sys.argv[3]
            ocr_enabled = "--no-ocr" not in sys.argv
            dpi = 150
            if "--dpi" in sys.argv:
                idx = sys.argv.index("--dpi")
                if idx + 1 < len(sys.argv):
                    dpi = int(sys.argv[idx + 1])
            prepare(pdf_path, output_dir, ocr_enabled=ocr_enabled, dpi=dpi)

        elif command == "build_plan":
            if len(sys.argv) < 3:
                print("Error: build_plan requires <output_dir>", file=sys.stderr)
                sys.exit(1)
            output_dir = sys.argv[2]
            disclaimer_json = sys.argv[3] if len(sys.argv) > 3 else "[]"
            build_plan(output_dir, disclaimer_json)

    except Exception as exc:
        logger.error("convert_auto failed", command=command, error=str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
